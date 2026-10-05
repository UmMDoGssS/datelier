import os
from pathlib import Path
from time import monotonic, sleep

import numpy as np
import polars as pl
import pytest

from datelier.analysis.jobs import AnalysisJobs
from datelier.analysis.types import (
    AnalysisRequest,
    EmbeddingResult,
    PreparedInput,
    Provenance,
)
from datelier.core.dataset import Dataset, SourceReference


def fake_result(prepared: PreparedInput) -> EmbeddingResult:
    return EmbeddingResult(
        prepared.revision,
        prepared.row_ids,
        prepared.positions,
        prepared.values[:, :2],
        Provenance(prepared.request, prepared.summary, (), 0),
    )


def failed_result(prepared: PreparedInput) -> EmbeddingResult:
    raise ValueError("deliberate worker error")


def slow_result(prepared: PreparedInput) -> EmbeddingResult:
    sleep(10)
    return fake_result(prepared)


def crashing_result(prepared: PreparedInput) -> EmbeddingResult:
    if prepared.request.seed == 17:
        os._exit(7)
    return fake_result(prepared)


def dataset() -> Dataset:
    return Dataset.from_source(
        pl.DataFrame({"x": range(30), "y": np.sin(np.arange(30))}),
        SourceReference(Path("unused"), 0, 0),
    )


def wait(jobs: AnalysisJobs, data: Dataset) -> None:
    deadline = monotonic() + 10
    while jobs.busy and monotonic() < deadline:
        jobs.poll(data.revision)
        sleep(0.01)
    assert not jobs.busy


def test_spawn_publication_and_revision_invalidation() -> None:
    data = dataset()
    jobs = AnalysisJobs(fake_result)
    try:
        assert not jobs.busy and not jobs.results
        jobs.request(data, AnalysisRequest(("x", "y")))
        with pytest.raises(ValueError):
            jobs.request(data, AnalysisRequest(("x", "y")))
        wait(jobs, data)
        assert len(jobs.results) == 1
        previous = jobs.latest
        assert previous is not None and not previous.row_ids.flags.writeable
        jobs.request(data, AnalysisRequest(("missing",)))
        wait(jobs, data)
        assert jobs.latest is previous and len(jobs.results) == 1
        assert "failed" in jobs.message
        jobs.poll(dataset().revision)
        assert not jobs.results
    finally:
        jobs.close()


def test_cancel_worker_and_reject_stale() -> None:
    data = dataset()
    jobs = AnalysisJobs(slow_result)
    try:
        jobs.request(data, AnalysisRequest(("x", "y")))
        deadline = monotonic() + 5
        while "fitting" not in jobs.phase and monotonic() < deadline:
            sleep(0.01)
        assert jobs.busy
        jobs.cancel()
        assert "requested" in jobs.message
        wait(jobs, data)
        assert "stopped" in jobs.message and not jobs.results
        jobs.request(data, AnalysisRequest(("x", "y")))
        jobs.poll(dataset().revision)
        wait(jobs, data)
        assert not jobs.results
    finally:
        jobs.close()


def test_preparation_and_worker_errors_are_visible() -> None:
    data = dataset()
    jobs = AnalysisJobs(failed_result)
    try:
        jobs.request(data, AnalysisRequest(("missing",)))
        wait(jobs, data)
        assert "failed" in jobs.message
        jobs.request(data, AnalysisRequest(("x", "y")))
        wait(jobs, data)
        assert "deliberate worker error" in jobs.message
    finally:
        jobs.close()


def test_actual_tsne_cancellation_has_no_publication() -> None:
    from datelier.analysis.types import TSNEParameters

    data = dataset()
    jobs = AnalysisJobs()
    try:
        jobs.request(data, AnalysisRequest(("x", "y"), TSNEParameters(perplexity=5)))
        deadline = monotonic() + 5
        while "fitting" not in jobs.phase and monotonic() < deadline:
            sleep(0.01)
        jobs.cancel()
        wait(jobs, data)
        assert not jobs.results and "stopped" in jobs.message
    finally:
        jobs.close()


def test_cancel_completed_worker_before_publication() -> None:
    data = dataset()
    jobs = AnalysisJobs(fake_result)
    try:
        jobs.request(data, AnalysisRequest(("x", "y")))
        assert jobs._future is not None
        jobs._future.result(timeout=10)
        jobs.cancel()
        jobs.poll(data.revision)
        assert not jobs.busy and not jobs.results
        assert "stopped" in jobs.message
    finally:
        jobs.close()


def test_abrupt_worker_exit_retains_result_and_allows_retry() -> None:
    data = dataset()
    jobs = AnalysisJobs(crashing_result)
    try:
        jobs.request(data, AnalysisRequest(("x", "y")))
        wait(jobs, data)
        previous = jobs.latest
        assert previous is not None
        jobs.request(data, AnalysisRequest(("x", "y"), seed=17))
        wait(jobs, data)
        assert "worker exited" in jobs.message.lower() and "(7)" in jobs.message
        assert jobs.latest is previous and len(jobs.results) == 1
        jobs.request(data, AnalysisRequest(("x", "y"), seed=18))
        wait(jobs, data)
        assert jobs.latest is not None and jobs.latest is not previous
        assert jobs.latest.provenance.request.seed == 18
    finally:
        jobs.close()
