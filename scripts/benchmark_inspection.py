"""Measure the real CSV/import/page/job contracts in fresh Linux processes."""

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
from time import perf_counter, sleep

import polars as pl

from datelier.feasibility.fixtures import make_table
from datelier.inspection.table import (
    PAGE_COLUMNS,
    PAGE_ROWS,
    prepare_inspection,
    prepare_page,
)
from datelier.io.csv import load_csv
from datelier.io.loading import DatasetLoader, LoadPhase

CASES = ((10_000, 6), (100_000, 6), (1_000_000, 6), (100_000, 64))


def measure(rows: int, columns: int) -> dict[str, int | float]:
    expected = make_table(rows, columns)
    with TemporaryDirectory(prefix="datelier-inspection-benchmark-") as directory:
        path = Path(directory) / "fixture.csv"
        expected.write_csv(path)
        source_stat = path.stat()
        started = perf_counter()
        imported = load_csv(path)
        read = perf_counter()
        inspection = prepare_inspection(imported)
        prepared = perf_counter()
        last = prepare_page(imported.dataset, rows - PAGE_ROWS, max(0, columns - 2))
        paged = perf_counter()
        loader = DatasetLoader()
        try:
            requested = perf_counter()
            loader.request(path)
            while loader.status.phase == LoadPhase.LOADING:
                loader.poll()
                sleep(0.001)
                if perf_counter() - requested > 10:
                    raise TimeoutError("Background load exceeded ten seconds")
            completed = perf_counter()
            assert loader.active is not None
            assert loader.status.phase == LoadPhase.READY
        finally:
            loader.close()
        loaded = imported.dataset.table
        assert loaded.with_columns(pl.col("row_id").cast(pl.UInt64)).equals(expected)
        assert imported.dataset.row_ids.equals(
            pl.int_range(0, rows, dtype=pl.UInt64, eager=True)
        )
        assert len(inspection.first_page.rows) == PAGE_ROWS
        assert len(inspection.first_page.columns) <= PAGE_COLUMNS
        assert [summary.null_count for summary in inspection.schema] == list(
            expected.null_count().row(0)
        )
        assert last.row_ids[0] == rows - PAGE_ROWS
        assert last.row_ids[-1] == rows - 1
        after = path.stat()
        assert (after.st_size, after.st_mtime_ns) == (
            source_stat.st_size,
            source_stat.st_mtime_ns,
        )
        return {
            "rows": rows,
            "columns": expected.width,
            "csv_import_ms": (read - started) * 1000,
            "inspection_ms": (prepared - read) * 1000,
            "csv_to_prepared_ms": (prepared - started) * 1000,
            "last_page_ms": (paged - prepared) * 1000,
            "background_to_prepared_ms": (completed - requested) * 1000,
            "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=int, nargs=2)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-inspection-benchmark.json")
    )
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(measure(*args.worker)))
        return
    measurements: list[dict[str, int | float]] = []
    for rows, columns in CASES:
        for _ in range(3):
            result = subprocess.run(
                [sys.executable, __file__, "--worker", str(rows), str(columns)],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            measurements.append(json.loads(result.stdout))
        print(f"Measured {rows:,} rows × {columns + 2} columns", flush=True)
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu": next(
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        ),
        "logical_cpus": os.cpu_count(),
        "ram_bytes": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
        "polars_threads": pl.thread_pool_size(),
        "versions": {
            name: version(name) for name in ("polars", "imgui-bundle", "numpy")
        },
        "fixture_types": "UInt64 row_id, Float64 numeric features, String category",
        "repeats": 3,
        "measurements": measurements,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
