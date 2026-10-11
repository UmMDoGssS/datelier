from dataclasses import replace
from pathlib import Path

import polars as pl
import pytest

from datelier.inspection.preview import PreviewCache
from datelier.inspection.table import prepare_inspection
from datelier.io.exporting import ExportFormat, export_dataset
from datelier.io.importing import load_file
from datelier.pipeline.history import Pipeline, replay
from datelier.pipeline.operations import Comparison, Filter, SelectColumns, Sort
from datelier.pipeline.transforms import (
    CastColumn,
    DerivedColumn,
    FillMissing,
    Lookup,
    TargetType,
    Unmatched,
)


@pytest.mark.parametrize("suffix", ["csv", "tsv", "json", "jsonl", "parquet", "xml"])
def test_each_format_transform_history_preview_replay_export(
    tmp_path: Path, suffix: str
) -> None:
    table = pl.DataFrame(
        {"id": [3, 1, 2], "value": [3.5, None, 1.5], "label": ["c", "a", "b"]}
    )
    path = tmp_path / f"source.{suffix}"
    if suffix in ("csv", "tsv"):
        table.write_csv(path, separator="\t" if suffix == "tsv" else ",")
    elif suffix == "json":
        table.write_json(path)
    elif suffix == "jsonl":
        table.write_ndjson(path)
    elif suffix == "parquet":
        table.write_parquet(path)
    else:
        path.write_text(
            "<rows><row><id>3</id><value>3.5</value><label>c</label></row><row><id>1</id><value/><label>a</label></row><row><id>2</id><value>1.5</value><label>b</label></row></rows>"
        )
    original = path.read_bytes()
    imported = load_file(path)
    pages = PreviewCache()
    pages.bind(prepare_inspection(imported))
    pipeline = Pipeline.start(imported.dataset)
    try:
        for operation in (
            Sort(("id",)),
            Filter("id", Comparison.LE, 2),
            FillMissing("value", 0),
            CastColumn("id", TargetType.TEXT),
            Lookup(
                "label",
                (("a", "first"), ("b", "second")),
                TargetType.TEXT,
                Unmatched.ERROR,
            ),
            DerivedColumn("score", 'col("value") * 2 + 1'),
            SelectColumns(("label", "score", "id")),
        ):
            previous = pipeline.current.revision
            pipeline = pipeline.apply(operation)
            inspection = prepare_inspection(replace(imported, dataset=pipeline.current))
            pages.bind(inspection)
            page = pages.get(0)
            assert page is not None and page.revision != previous
            assert page.revision == pipeline.current.revision
        assert pipeline.current.table.rows() == [
            ("first", 1.0, "1"),
            ("second", 4.0, "2"),
        ]
        assert pipeline.current.row_ids.to_list() == [1, 2]
        repeated = replay(pipeline.source, pipeline.operations)
        assert repeated.table.equals(pipeline.current.table)
        assert repeated.row_ids.equals(pipeline.current.row_ids)
        restored = pipeline
        while restored.can_undo:
            restored = restored.undo()
        assert restored.current.table.equals(table)
        while restored.can_redo:
            restored = restored.redo()
        assert restored.current.table.equals(pipeline.current.table)
        for format in ExportFormat:
            output = tmp_path / (
                "result.csv" if format == ExportFormat.CSV else "result.parquet"
            )
            export_dataset(pipeline.current, output, format)
            # CSV's textual values need an explicit string schema for numeric text.
            actual = (
                pl.read_csv(output, schema_overrides={"id": pl.String})
                if format == ExportFormat.CSV
                else pl.read_parquet(output)
            )
            assert actual.equals(pipeline.current.table)
        assert path.read_bytes() == original
    finally:
        pages.close()


@pytest.mark.parametrize("format", list(ExportFormat))
def test_empty_and_literal_text_export(tmp_path: Path, format: ExportFormat) -> None:
    path = tmp_path / "source.csv"
    path.write_text('^x$,text\n1,"café\nnext"\n2,""\n')
    pipeline = Pipeline.start(load_file(path).dataset)
    output = tmp_path / "output"
    export_dataset(pipeline.current, output, format)
    loaded = (
        pl.read_csv(output) if format == ExportFormat.CSV else pl.read_parquet(output)
    )
    assert loaded.equals(pipeline.current.table)
    empty = pipeline.apply(Filter("^x$", Comparison.LT, 0))
    export_dataset(empty.current, output, format, overwrite=True)
    loaded = (
        pl.read_csv(output) if format == ExportFormat.CSV else pl.read_parquet(output)
    )
    assert loaded.shape == (0, 2)
    assert loaded.columns == ["^x$", "text"]
