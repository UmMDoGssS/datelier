from pathlib import Path
from time import monotonic, sleep

import polars as pl
import pytest

from datelier.io.jobs import (
    DatasetExporter,
    ExportFailure,
    ExportFormat,
    export_dataset,
)
from datelier.io.tabular import load_csv
from datelier.pipeline import Comparison, Filter, Pipeline, SelectColumns, Sort
from datelier.pipeline.transforms import DerivedColumn


def pipeline(path: Path) -> Pipeline:
    path.write_text('v,label\n3,"a,b"\n1,""\n2,\n')
    return (
        Pipeline.start(load_csv(path).dataset)
        .apply(Sort(("v",)))
        .apply(Filter("v", Comparison.GE, 2))
        .apply(DerivedColumn("double", 'col("v") * 2'))
        .apply(SelectColumns(("label", "double")))
    )


@pytest.mark.parametrize("format", list(ExportFormat))
def test_export_roundtrip_active_values_identity_and_source(
    tmp_path: Path, format: ExportFormat
) -> None:
    source = tmp_path / "source.csv"
    recipe = pipeline(source)
    original = source.read_bytes()
    output = tmp_path / (
        "export.csv" if format == ExportFormat.CSV else "export.parquet"
    )
    result = export_dataset(recipe.current, output, format)
    actual = (
        pl.read_csv(output) if format == ExportFormat.CSV else pl.read_parquet(output)
    )
    assert actual.equals(recipe.current.table)
    assert result.revision == recipe.current.revision
    assert result.rows == 2 and result.columns == 2
    assert source.read_bytes() == original
    assert not list(tmp_path.glob(".datelier-export-*"))
    assert recipe.current.row_ids.to_list() == [2, 0]


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_source_aliases_cannot_be_overwritten(tmp_path: Path, alias: str) -> None:
    source = tmp_path / "source.csv"
    recipe = pipeline(source)
    original = source.read_bytes()
    output = source if alias == "same" else tmp_path / "alias.csv"
    if alias == "symlink":
        output.symlink_to(source)
    elif alias == "hardlink":
        output.hardlink_to(source)
    with pytest.raises(ExportFailure, match="source files"):
        export_dataset(recipe.current, output, ExportFormat.CSV, overwrite=True)
    assert source.read_bytes() == original


def test_existing_destinations_and_failed_write_are_preserved(
    tmp_path: Path, monkeypatch
) -> None:
    recipe = pipeline(tmp_path / "source.csv")
    output = tmp_path / "export.csv"
    output.write_text("old result")
    with pytest.raises(ExportFailure, match="exists"):
        export_dataset(recipe.current, output, ExportFormat.CSV)
    assert output.read_text() == "old result"
    export_dataset(recipe.current, output, ExportFormat.CSV, overwrite=True)
    saved = output.read_bytes()

    def failed(self: pl.DataFrame, file: Path) -> None:
        file.write_text("partial")
        raise OSError("disk full")

    monkeypatch.setattr(pl.DataFrame, "write_csv", failed)
    with pytest.raises(ExportFailure, match="disk full"):
        export_dataset(recipe.current, output, ExportFormat.CSV, overwrite=True)
    assert output.read_bytes() == saved
    assert not list(tmp_path.glob(".datelier-export-*"))


def test_destination_created_during_export_is_not_overwritten(
    tmp_path: Path, monkeypatch
) -> None:
    recipe = pipeline(tmp_path / "source.csv")
    output = tmp_path / "export.csv"
    original = pl.DataFrame.write_csv

    def raced(self: pl.DataFrame, file: Path) -> None:
        original(self, file)
        output.write_text("another writer")

    monkeypatch.setattr(pl.DataFrame, "write_csv", raced)
    with pytest.raises(ExportFailure, match="exists"):
        export_dataset(recipe.current, output, ExportFormat.CSV)
    assert output.read_text() == "another writer"
    assert not list(tmp_path.glob(".datelier-export-*"))


def test_export_job_and_closed_exporter(tmp_path: Path) -> None:
    recipe = pipeline(tmp_path / "source.csv")
    exporter = DatasetExporter()
    try:
        exporter.request(
            recipe.current, tmp_path / "export.parquet", ExportFormat.PARQUET
        )
        deadline = monotonic() + 3
        while exporter.busy and monotonic() < deadline:
            exporter.poll()
            sleep(0.001)
        assert not exporter.busy and exporter.result is not None
        assert exporter.result.revision == recipe.current.revision
        assert "Exported 2 rows" in exporter.message
    finally:
        exporter.close()
    with pytest.raises(ValueError, match="idle"):
        exporter.request(recipe.current, tmp_path / "other.csv", ExportFormat.CSV)


def test_export_preserves_another_open_source(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    recipe = pipeline(source)
    sibling = tmp_path / "sibling.csv"
    sibling.write_bytes(b"x\n42\n")
    alias = tmp_path / "sibling-alias.csv"
    alias.hardlink_to(sibling)
    original = sibling.read_bytes()
    with pytest.raises(ExportFailure, match="source files are preserved"):
        export_dataset(
            recipe.current, alias, ExportFormat.CSV, overwrite=True, sources=(sibling,)
        )
    assert sibling.read_bytes() == original
    assert not list(tmp_path.glob(".datelier-export-*"))
