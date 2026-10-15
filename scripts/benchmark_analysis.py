"""Fresh parent + spawned worker resource evidence for bounded analysis."""

import argparse
import json
import os
import resource
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter, sleep

from support.tables import make_table

from datelier.analysis.algorithms import ALGORITHMS
from datelier.analysis.jobs import AnalysisJobs
from datelier.analysis.parameters import DBSCANParameters
from datelier.analysis.types import (
    DEFAULT_LIMITS,
    Algorithm,
    AnalysisRequest,
    ClusteringResult,
)
from datelier.core import Dataset, SourceReference


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--algorithm", choices=[a.name.lower() for a in Algorithm], required=True
    )
    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument("--columns", type=int, default=6)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cancel", action="store_true")
    parser.add_argument("--sample-limit", type=int)
    parser.add_argument("--dense-neighborhood", action="store_true")
    args = parser.parse_args()
    dataset = Dataset.from_source(
        make_table(args.rows, args.columns), SourceReference(Path("synthetic"), 0, 0)
    )
    algorithm = next(a for a in Algorithm if a.name.lower() == args.algorithm)
    parameters = ALGORITHMS[algorithm]()
    if args.dense_neighborhood:
        if args.algorithm != "dbscan":
            raise ValueError("Dense-neighborhood measurement requires DBSCAN")
        parameters = DBSCANParameters(epsilon=1e6)
    request = AnalysisRequest(
        tuple(f"feature_{i}" for i in range(args.columns)),
        parameters,
        row_limit=args.sample_limit or DEFAULT_LIMITS[parameters.algorithm],
    )
    if args.cancel:
        report = measure_cancellation(dataset, request)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
        return
    cache = TemporaryDirectory(prefix="datelier-analysis-numba-")
    os.environ["NUMBA_CACHE_DIR"] = cache.name
    jobs = AnalysisJobs()
    timings: list[dict[str, float]] = []
    try:
        for _ in range(2):
            started = perf_counter()
            jobs.request(dataset, request)
            while jobs.busy and perf_counter() - started < 300:
                jobs.poll(dataset.revision)
                sleep(0.01)
            if jobs.busy or jobs.latest is None or "failed" in jobs.message:
                raise RuntimeError(jobs.message)
            timings.append(
                {
                    "wall_seconds": perf_counter() - started,
                    "fit_seconds": jobs.latest.provenance.runtime_seconds,
                }
            )
        result = jobs.latest
        assert result is not None
        if isinstance(result, ClusteringResult):
            assert (
                sum(result.counts) + result.noise_count
                == result.provenance.input.sampled_rows
            )
        parent = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        child = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
        report = {
            "algorithm": str(request.algorithm),
            "parameters": asdict(request.parameters),
            "preprocessing": asdict(request.preprocessing),
            "row_limit": request.row_limit,
            "dimensions": request.dimensions,
            "seed": request.seed,
            "rows": args.rows,
            "features": args.columns,
            "sample": asdict(result.provenance.input),
            "versions": result.provenance.versions,
            "cold_then_warmed_spawn": timings,
            "parent_peak_mib": parent,
            "worker_peak_mib": child,
            "combined_peak_upper_bound_mib": parent + child,
            "memory_budget_mib": 2048,
            "memory_passed": parent + child <= 2048,
        }
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
        assert report["memory_passed"]
    finally:
        jobs.close()
        cache.cleanup()


def measure_cancellation(
    dataset: Dataset, request: AnalysisRequest
) -> dict[str, object]:
    jobs = AnalysisJobs()
    try:
        started = perf_counter()
        jobs.request(dataset, request)
        while "fitting" not in jobs.phase and perf_counter() - started < 30:
            sleep(0.01)
        assert "fitting" in jobs.phase
        # Allow the worker to enter imports/fitting, without relying on an
        # estimator-specific progress callback that these libraries don't offer.
        sleep(0.25)
        phase = jobs.phase
        cancel_started = perf_counter()
        jobs.cancel()
        while jobs.busy and perf_counter() - cancel_started < 10:
            jobs.poll(dataset.revision)
            sleep(0.01)
        assert not jobs.busy and not jobs.results and "stopped" in jobs.message
        return {
            "algorithm": str(request.algorithm),
            "rows": dataset.table.height,
            "sample_limit": request.row_limit,
            "phase_at_cancel": phase,
            "start_to_cancel_seconds": cancel_started - started,
            "cancel_to_confirmed_exit_seconds": perf_counter() - cancel_started,
            "published_results": len(jobs.results),
            "message": jobs.message,
        }
    finally:
        jobs.close()


if __name__ == "__main__":
    main()
