from dataclasses import replace
from pathlib import Path
from threading import Event, current_thread, main_thread
from time import monotonic, sleep

import polars as pl
import pytest

from datelier.core.dataset import Dataset, SourceReference
from datelier.core.jobs import SharedWorkers
from datelier.inspection.comparison_settings import ComparisonSettings, ComparisonSource
from datelier.inspection.comparisons import jobs as module
from datelier.inspection.comparisons.jobs import ComparisonJobs
from datelier.inspection.comparisons.types import (
    ComparisonInput,
    ComparisonSelection,
    PreparedComparison,
)
from datelier.pipeline.operations import Sort, apply_operation


def sources() -> dict[str, Dataset]:
    return {
        name: Dataset.from_source(
            pl.DataFrame({"x": [3.0, 0.0, 2.0, 1.0]}), SourceReference(Path(name), 0, 0)
        )
        for name in ("train", "test", "third")
    }


def recipe(*names: str) -> ComparisonSettings:
    return ComparisonSettings(
        tuple(ComparisonSource(name, "x") for name in names), bins=2
    )


def wait(
    jobs: ComparisonJobs,
    recipes: tuple[ComparisonSettings, ...],
    data: dict[str, Dataset],
) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        jobs.sync(recipes, data)
        if not jobs.busy:
            return
        sleep(0.001)
    raise AssertionError("Comparison did not finish")


def test_only_affected_results_recompute_and_owner_close_releases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = module.prepare_comparison
    threads: list[bool] = []

    def guarded(
        inputs: tuple[ComparisonInput, ...], settings: ComparisonSettings
    ) -> PreparedComparison:
        threads.append(current_thread() is not main_thread())
        return original(inputs, settings)

    monkeypatch.setattr(module, "prepare_comparison", guarded)
    data = sources()
    recipes = (recipe("train", "test"), recipe("test", "third"))
    with SharedWorkers() as workers:
        jobs = ComparisonJobs(executor=workers)
        wait(jobs, recipes, data)
        affected, retained = (s.result for s in jobs.states)
        assert affected is not None and retained is not None
        data["train"] = apply_operation(data["train"], Sort(("x",)))
        jobs.sync(recipes, data)
        assert jobs.states[0].result is None and jobs.states[1].result is retained
        wait(jobs, recipes, data)
        assert (
            jobs.states[0].result is not affected and jobs.states[1].result is retained
        )
        assert jobs.started == 3 and threads == [True, True, True]
        jobs.sync(recipes, {"test": data["test"], "third": data["third"]})
        assert (
            "unavailable" in jobs.states[0].message
            and jobs.states[1].result is retained
        )
        jobs.close()
        jobs.sync(recipes, data)
        assert not jobs.states and not jobs.busy


def test_executing_obsolete_result_does_not_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered, release = Event(), Event()
    original = module.prepare_comparison
    first = True

    def blocked(
        inputs: tuple[ComparisonInput, ...], settings: ComparisonSettings
    ) -> PreparedComparison:
        nonlocal first
        if first:
            first = False
            entered.set()
            assert release.wait(5)
        return original(inputs, settings)

    monkeypatch.setattr(module, "prepare_comparison", blocked)
    data, recipes = sources(), (recipe("train", "test"),)
    with SharedWorkers() as workers:
        jobs = ComparisonJobs(executor=workers)
        try:
            jobs.sync(recipes, data)
            assert entered.wait(5)
            data["train"] = apply_operation(data["train"], Sort(("x",)))
            jobs.sync(recipes, data)
            release.set()
            wait(jobs, recipes, data)
            result = jobs.states[0].result
            assert (
                result is not None
                and result.series[0].origin.revision == data["train"].revision
            )
            jobs.sync((), data)
            assert not jobs.states
        finally:
            release.set()
            jobs.close()


def test_selection_job_is_worker_bound_and_ignores_closed_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered, release = Event(), Event()
    original = module.select_bin

    def blocked(
        result: PreparedComparison, series: int, bin_index: int, dataset: Dataset
    ) -> ComparisonSelection:
        assert current_thread() is not main_thread()
        entered.set()
        assert release.wait(5)
        return original(result, series, bin_index, dataset)

    monkeypatch.setattr(module, "select_bin", blocked)
    data, recipes = sources(), (recipe("train", "test"),)
    with SharedWorkers() as workers:
        jobs = ComparisonJobs(executor=workers)
        try:
            wait(jobs, recipes, data)
            result = jobs.states[0].result
            assert result is not None
            jobs.request_selection(result, 0, 0, data["train"])
            assert entered.wait(5)
            release.set()
            deadline = monotonic() + 5
            while jobs.busy and monotonic() < deadline:
                assert jobs.poll_selection({"test": data["test"]}) is None
                sleep(0.001)
            assert "closed" in jobs.selection_message
            with pytest.raises(ValueError, match="changed"):
                jobs.request_selection(
                    result, 0, 0, apply_operation(data["train"], Sort(("x",)))
                )
            jobs.sync((replace(recipes[0], bins=3),), data)
            with pytest.raises(ValueError, match="changed"):
                jobs.request_selection(result, 0, 0, data["train"])
        finally:
            release.set()
            jobs.close()


def test_invalid_mapping_error_and_missing_file_do_not_schedule() -> None:
    jobs = ComparisonJobs()
    try:
        data = sources()
        jobs.sync((recipe("train"), recipe("train", "missing")), data)
        assert jobs.started == 0 and not jobs.busy
        invalid = ComparisonSettings(
            (ComparisonSource("train", "wrong"), ComparisonSource("test", "x"))
        )
        wait(jobs, (invalid,), data)
        assert jobs.states[0].result is None and "unavailable" in jobs.states[0].message
    finally:
        jobs.close()


def test_update_retries_a_saturated_worker_failure_without_changing_recipe() -> None:
    release, entered = Event(), Event()

    def hold() -> None:
        entered.set()
        assert release.wait(5)

    with SharedWorkers(workers=1, capacity=1) as workers:
        held = workers.submit(hold)
        assert entered.wait(5)
        jobs = ComparisonJobs(executor=workers)
        try:
            recipes, data = (recipe("train", "test"),), sources()
            jobs.sync(recipes, data)
            jobs.sync(recipes, data)
            assert "Retry" in jobs.states[0].message and jobs.states[0].result is None
            release.set()
            held.result(timeout=5)
            jobs.retry(recipes[0])
            wait(jobs, recipes, data)
            assert jobs.states[0].result is not None
        finally:
            release.set()
            jobs.close()
