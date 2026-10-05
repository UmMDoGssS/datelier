"""Fresh-process import measurements for new formats and baseline-sized fixtures."""

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
from xml.sax.saxutils import escape

import polars as pl

from datelier.feasibility.fixtures import make_table
from datelier.inspection import prepare_inspection, prepare_page
from datelier.io.importing import load_file
from datelier.io.types import ImportFormat

CASES = ((10_000, 6), (100_000, 6), (1_000_000, 6), (100_000, 64))


def measure(
    format: ImportFormat, rows: int, columns: int
) -> dict[str, str | int | float]:
    expected = make_table(rows, columns)
    with TemporaryDirectory(prefix="datelier-formats-benchmark-") as directory:
        path = Path(directory) / ("fixture." + format.lower())
        if format == ImportFormat.TSV:
            expected.write_csv(path, separator="\t")
        elif format == ImportFormat.JSON:
            expected.write_json(path)
        elif format == ImportFormat.JSONL:
            expected.write_ndjson(path)
        elif format == ImportFormat.PARQUET:
            expected.write_parquet(path)
        else:
            with path.open("w") as output:
                output.write("<rows>")
                for row in expected.iter_rows():
                    output.write("<row>")
                    for name, value in zip(expected.columns, row, strict=True):
                        text = "" if value is None else escape(str(value))
                        output.write(f"<{name}>{text}</{name}>")
                    output.write("</row>")
                output.write("</rows>")
        source_stat = path.stat()
        started = perf_counter()
        imported = load_file(path)
        read = perf_counter()
        inspection = prepare_inspection(imported)
        prepared = perf_counter()
        last = prepare_page(imported.dataset, rows - 100, max(0, columns - 2))
        paged = perf_counter()
        loaded = imported.dataset.table
        assert loaded.with_columns(pl.col("row_id").cast(pl.UInt64)).equals(expected)
        assert imported.dataset.row_ids.equals(
            pl.int_range(0, rows, dtype=pl.UInt64, eager=True)
        )
        assert last.row_ids == tuple(range(rows - 100, rows))
        assert [s.null_count for s in inspection.schema] == list(
            expected.null_count().row(0)
        )
        assert len(inspection.first_page.rows) == 100
        after = path.stat()
        assert (after.st_size, after.st_mtime_ns) == (
            source_stat.st_size,
            source_stat.st_mtime_ns,
        )
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        assert peak <= 1024, f"Peak RSS exceeded fixture budget: {peak}"
        assert (prepared - read) * 1000 <= 250, "Summary budget exceeded"
        assert (paged - prepared) * 1000 <= 50, "Page budget exceeded"
        return {
            "format": str(format),
            "rows": rows,
            "columns": expected.width,
            "source_bytes": after.st_size,
            "import_ms": (read - started) * 1000,
            "inspection_ms": (prepared - read) * 1000,
            "to_prepared_ms": (prepared - started) * 1000,
            "last_page_ms": (paged - prepared) * 1000,
            "peak_rss_mib": peak,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=int, nargs=2)
    parser.add_argument(
        "--format", choices=[str(f) for f in ImportFormat if f != ImportFormat.CSV]
    )
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-formats-benchmark.json")
    )
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(measure(ImportFormat(args.format), *args.worker)))
        return
    measurements: list[dict[str, str | int | float]] = []
    formats = (
        [ImportFormat(args.format)]
        if args.format
        else [f for f in ImportFormat if f != ImportFormat.CSV]
    )
    for format in formats:
        for rows, columns in CASES:
            result = subprocess.run(
                [
                    sys.executable,
                    __file__,
                    "--format",
                    str(format),
                    "--worker",
                    str(rows),
                    str(columns),
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=180,
            )
            measurements.append(json.loads(result.stdout))
            print(f"{format}: {rows:,} × {columns + 2}", flush=True)
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
        "fixture_types": (
            "UInt64 row_id, Float64 features, String category; "
            "null every 17 rows in last feature"
        ),
        "component_budgets": {
            "peak_rss_mib": 1024,
            "inspection_ms": 250,
            "last_page_ms": 50,
        },
        "repeats": 1,
        "measurements": measurements,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
