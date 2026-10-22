"""Frozen verification entry; uses only modules collected for the production app.

The helper is not shipped. Its spawned processes execute the production binary,
so a missing freeze_support dispatch fails this gate rather than going unnoticed.
"""

import argparse
import json
import multiprocessing as mp
import sys
from importlib.metadata import version
from pathlib import Path
from time import monotonic, sleep
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datelier.core import Dataset


def analyses(data: Dataset) -> list[str]:
    import numpy as np

    from datelier.analysis.jobs import AnalysisJobs
    from datelier.analysis.types import (
        AnalysisRequest,
        KMeansParameters,
        PCAParameters,
        TSNEParameters,
        UMAPParameters,
    )

    jobs = AnalysisJobs()
    completed: list[str] = []

    def wait() -> None:
        deadline = monotonic() + 180
        while jobs.busy and monotonic() < deadline:
            jobs.poll(data.revision)
            sleep(0.01)
        assert not jobs.busy, jobs.message

    try:
        for method in (
            PCAParameters(),
            KMeansParameters(),
            TSNEParameters(perplexity=5, iterations=250),
            UMAPParameters(neighbors=5),
        ):
            request = AnalysisRequest(("x", "y", "z"), method)
            jobs.request(data, request)
            wait()
            result = jobs.latest
            assert result is not None and result.provenance.request == request, (
                jobs.message
            )
            np.testing.assert_array_equal(result.row_ids, data.row_ids.to_numpy())
            assert all(value for _, value in result.provenance.versions)
            completed.append(request.algorithm.value)
            print(f"Verified frozen {request.algorithm}", flush=True)
        previous = jobs.latest
        jobs.request(data, AnalysisRequest(("x", "y", "z"), TSNEParameters(), seed=123))
        deadline = monotonic() + 10
        while not jobs.phase.startswith("Loading libraries") and monotonic() < deadline:
            sleep(0.005)
        assert jobs.busy and jobs.phase.startswith("Loading libraries"), jobs.phase
        jobs.cancel()
        wait()
        assert jobs.latest is previous and "cancelled" in jobs.message.lower()
    finally:
        jobs.close()
    return completed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert getattr(sys, "frozen", False), "Run the built datelier-verify executable"
    assert "torch" not in sys.modules and "sounddevice" not in sys.modules
    mp.set_executable(str(Path(sys.executable).with_name("datelier")))
    import numpy as np
    import polars as pl

    from datelier.io.importing import load_file

    args.output.mkdir(parents=True, exist_ok=True)
    source = args.output / "data.csv"
    rng = np.random.default_rng(42)
    table = pl.DataFrame({name: rng.normal(size=80) for name in ("x", "y", "z")})
    table.write_csv(source)
    before = source.read_bytes()
    data = load_file(source).dataset
    report = {
        "version": version("datelier"),
        "analyses": analyses(data),
        "cancelled_worker_joined": True,
    }
    assert source.read_bytes() == before
    (args.output / "frozen-verification.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    mp.freeze_support()
    main()
