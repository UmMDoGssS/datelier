"""Measure exact streamed list text profiles and direct single-element access."""

import argparse
import json
import platform
import resource
from pathlib import Path
from threading import Event
from time import perf_counter

import polars as pl

from datelier.core.dataset import Dataset, SourceReference
from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.text.profiles.corpus import TextProgress
from datelier.inspection.text.profiles.prepare import prepare_profile
from datelier.inspection.text.tokenizers.prepare import prepare_document
from datelier.inspection.text.types import CorpusMode, TextScope, TextSettings

BUDGETS = {
    "profile_seconds": 20,
    "selected_element_ms": 50,
    "retained_mib": 16,
    "peak_rss_mib": 512,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=25_000)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-list-text-resources.json")
    )
    args = parser.parse_args()
    if args.rows < 1:
        parser.error("Choose a positive row count")
    values = pl.Series(
        "text", [[["alpha beta beta", "café 中"], ["", None]]] * args.rows
    )
    source = SourceReference(Path("unused"), 0, 0)
    dataset = Dataset.from_source(values.to_frame(), source)
    settings = TextSettings("text", scope=TextScope(CorpusMode.COLLECTION))
    started = perf_counter()
    prepared = prepare_profile(
        dataset,
        "file",
        settings,
        (),
        ReferenceSettings(),
        None,
        Event(),
        TextProgress(),
    )
    elapsed = perf_counter() - started
    result = prepared.profile
    assert (
        result.requested_records,
        result.documents,
        result.nulls,
        result.empty,
        result.tokens,
    ) == (args.rows, args.rows * 3, args.rows, args.rows, args.rows * 5)
    assert result.records.height == args.rows * 4
    assert result.records["element_path"].head(4).to_list() == [
        [0, 0],
        [0, 1],
        [1, 0],
        [1, 1],
    ]
    assert result.vocabulary_size == 4
    assert dataset.table["text"].equals(values)
    assert dataset.row_ids.equals(
        pl.int_range(0, args.rows, dtype=pl.UInt64, eager=True)
    )
    many = Dataset.from_source(
        pl.DataFrame({"text": [["unchosen " * 64] * 99_999 + ["last element"]]}), source
    )
    started = perf_counter()
    document = prepare_document(
        many,
        "file",
        TextSettings("text", element_index=99_999),
        ReferenceSettings(),
        None,
    )
    selected_ms = (perf_counter() - started) * 1000
    assert (
        document.document.text == "last element"
        and document.document.origin.element_path == (99_999,)
    )
    measurements = {
        "profile_seconds": elapsed,
        "selected_element_ms": selected_ms,
        "retained_mib": prepared.retained_bytes / 1024**2,
        "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    }
    report = {
        "python": platform.python_version(),
        "polars": pl.__version__,
        "rows": args.rows,
        "elements": result.records.height,
        "tokens": result.tokens,
        **measurements,
        "source_values_and_ids_preserved": True,
        "budgets": BUDGETS,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    assert all(measurements[key] < budget for key, budget in BUDGETS.items())


if __name__ == "__main__":
    main()
