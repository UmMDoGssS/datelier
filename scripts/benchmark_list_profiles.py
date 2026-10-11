"""Measure exact nested list profiles and bounded, metadata-only table previews."""

import argparse
import json
import platform
import resource
from pathlib import Path
from time import perf_counter

import polars as pl

from datelier.core import Dataset, SourceReference
from datelier.inspection.profiles.preview import ProfileRequest, prepare_profile_group
from datelier.inspection.table import PAGE_ROWS, prepare_page
from datelier.plotting.distributions import DistributionSettings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-list-resources.json")
    )
    args = parser.parse_args()
    if args.rows < 1:
        parser.error("Choose a positive row count")
    started = perf_counter()
    source = pl.Series(
        "xs",
        [[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]] * args.rows,
        dtype=pl.List(pl.List(pl.Float64)),
    )
    dataset = Dataset.from_source(
        source.to_frame(), SourceReference(Path("unused"), 0, 0)
    )
    preview_started = perf_counter()
    page = prepare_page(dataset, 0)
    preview_ms = (perf_counter() - preview_started) * 1000
    profile_started = perf_counter()
    group = prepare_profile_group(
        dataset, ProfileRequest(DistributionSettings(("xs",), density=False))
    )
    profile_seconds = perf_counter() - profile_started
    profile = group.profiles.columns[0]
    assert profile.statistics and profile.statistics.mean == 3.5
    lists = profile.list_statistics
    assert lists and lists.elements == args.rows * 6
    assert lists.shapes == (("2 × 3", args.rows),)
    assert group.comparison and group.comparison.series[0].sample_count <= 2000
    assert len(page.rows) == min(args.rows, PAGE_ROWS)
    assert all(row == ("[ ... ] (2 items)",) for row in page.rows)
    assert dataset.table["xs"].equals(source)
    assert dataset.row_ids.equals(
        pl.int_range(0, args.rows, dtype=pl.UInt64, eager=True)
    )
    report = {
        "python": platform.python_version(),
        "polars": pl.__version__,
        "rows": args.rows,
        "leaf_elements": args.rows * 6,
        "shape": "2 × 3",
        "profile_seconds": profile_seconds,
        "preview_ms": preview_ms,
        "source_table_mib": dataset.table.estimated_size() / 1024**2,
        "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "total_seconds": perf_counter() - started,
        "source_values_and_ids_preserved": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
