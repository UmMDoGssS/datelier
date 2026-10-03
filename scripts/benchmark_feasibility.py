"""Fresh-process Linux benchmarks; large synthetic tables stay in temporary files."""

import argparse
import json
import os
import platform
import resource
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import cast

import polars as pl

from datelier.feasibility.fixtures import make_table
from datelier.feasibility.plot_data import DEFAULT_POINT_LIMIT, prepare_scatter

Measurement = dict[str, int | float]
CASES = ((10_000, 6), (100_000, 6), (1_000_000, 6), (100_000, 64))


def measure(rows: int, numeric_columns: int) -> Measurement:
    started = perf_counter()
    table = make_table(rows, numeric_columns)
    generated = perf_counter()
    with TemporaryDirectory(prefix="datelier-benchmark-") as directory:
        source = Path(directory) / "fixture.csv"
        table.write_csv(source)
        written = perf_counter()
        loaded = pl.read_csv(source, schema_overrides=table.schema)
        read = perf_counter()
        preview = tuple(
            tuple(str(value) for value in row)
            for row in loaded.select(loaded.columns[:8]).head(100).iter_rows()
        )
        previewed = perf_counter()
        loaded.null_count()
        loaded.select(pl.col(pl.Float64).mean())
        profiled = perf_counter()
        points = prepare_scatter(loaded, "feature_0", "feature_1")
        plotted = perf_counter()
        csv_bytes = source.stat().st_size
    if not table.equals(loaded) or len(preview) != min(rows, 100):
        raise RuntimeError("CSV roundtrip/preview invariant failed")
    if points.row_ids.tolist() != list(range(min(rows, DEFAULT_POINT_LIMIT))):
        raise RuntimeError("Plot identity/bound invariant failed")
    return {
        "rows": rows,
        "columns": table.width,
        "generation_seconds": generated - started,
        "csv_write_seconds": written - generated,
        "csv_read_seconds": read - written,
        "preview_seconds": previewed - read,
        "summary_seconds": profiled - previewed,
        "plot_prepare_seconds": plotted - profiled,
        "csv_bytes": csv_bytes,
        "table_estimated_bytes": loaded.estimated_size(),
        "plot_array_bytes": points.x.nbytes + points.y.nbytes + points.row_ids.nbytes,
        "plot_points": len(points.x),
        "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", nargs=2, type=int, metavar=("ROWS", "NUMERIC_COLS"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-benchmark.json")
    )
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(measure(*args.worker)))
        return
    if args.repeats < 1:
        parser.error("Require a positive repeat count")
    measurements: list[Measurement] = []
    for rows, columns in CASES:
        for _ in range(args.repeats):
            result = subprocess.run(
                [sys.executable, __file__, "--worker", str(rows), str(columns)],
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )
            # JSON is emitted by this script's worker with the Measurement schema.
            measurements.append(cast(Measurement, json.loads(result.stdout)))
        print(f"Measured {rows:,} rows × {columns + 2} columns", flush=True)
    cpu = next(
        line.split(":", 1)[1].strip()
        for line in Path("/proc/cpuinfo").read_text().splitlines()
        if line.startswith("model name")
    )
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu": cpu,
        "logical_cpus": os.cpu_count(),
        "ram_bytes": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
        "polars_threads": pl.thread_pool_size(),
        "versions": {
            name: version(name)
            for name in (
                "polars",
                "imgui-bundle",
                "numpy",
                "scikit-learn",
                "umap-learn",
                "numba",
            )
        },
        "repeats": args.repeats,
        "measurements": measurements,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
