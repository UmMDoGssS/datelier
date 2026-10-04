from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from datelier.import_types import ImportFailure, ImportFormat, ParquetOptions
from datelier.importing import load_file
from datelier.inspection import prepare_inspection


def test_parquet_preserves_types_nulls_values_identity_and_source(
    tmp_path: Path,
) -> None:
    table = pl.DataFrame(
        {
            "row_id": pl.Series([9, 3], dtype=pl.UInt32),
            "value": pl.Series([1.5, None], dtype=pl.Float32),
            "flag": [True, None],
            "label": ["café", "last"],
            "day": [date(2026, 10, 4), None],
            "time": [datetime(2026, 10, 4, 12), None],
            "money": [Decimal("1.25"), None],
            "binary": [b"hello", None],
        }
    )
    path = tmp_path / "fixture[1].PARQUET"
    table.write_parquet(path)
    content = path.read_bytes()
    imported = load_file(path)
    assert imported.format == ImportFormat.PARQUET
    assert_frame_equal(imported.dataset.table, table)
    assert imported.dataset.row_ids.to_list() == [0, 1]
    inspection = prepare_inspection(imported)
    assert inspection.schema[1].dtype == "Float32"
    assert inspection.schema[1].null_count == 1
    assert inspection.first_page.rows[1] == (
        "3",
        *("NULL",) * 2,
        "last",
        *("NULL",) * 4,
    )
    assert path.read_bytes() == content


def test_parquet_selected_columns_and_empty_schema(tmp_path: Path) -> None:
    path = tmp_path / "fixture.pq"
    pl.DataFrame({"a": [1], "b": ["two"]}).write_parquet(path)
    options = ParquetOptions(columns=("b",))
    imported = load_file(path, options)
    assert imported.options == options
    assert imported.dataset.table.rows() == [("two",)]
    assert "Only requested" in imported.diagnostics[1]
    with pytest.raises(ImportFailure, match="requested columns"):
        load_file(path, ParquetOptions(columns=("missing",)))
    pl.DataFrame(schema={"id": pl.Int64, "label": pl.String}).write_parquet(path)
    empty = load_file(path)
    assert empty.dataset.table.schema == {"id": pl.Int64, "label": pl.String}
    assert prepare_inspection(empty).first_page.rows == ()
    assert "no data rows" in empty.diagnostics[-1]


@pytest.mark.parametrize("values", [[[1, 2], []], [{"x": 1}, {"x": 2}]])
def test_nested_parquet_rejected_or_explicitly_excluded(
    tmp_path: Path, values: list[object]
) -> None:
    path = tmp_path / "nested.parquet"
    pl.DataFrame({"id": [1, 2], "nested": values}).write_parquet(path)
    with pytest.raises(ImportFailure, match="Nested Parquet.*nested"):
        load_file(path)
    imported = load_file(path, ParquetOptions(columns=("id",)))
    assert imported.dataset.table.rows() == [(1,), (2,)]


@pytest.mark.parametrize("content", [b"", b"not parquet", b"PAR1brokenPAR1"])
def test_corrupt_parquet_has_actionable_diagnostic(
    tmp_path: Path, content: bytes
) -> None:
    path = tmp_path / "bad.parquet"
    path.write_bytes(content)
    with pytest.raises(ImportFailure, match="valid Parquet"):
        load_file(path)
    assert path.read_bytes() == content


@pytest.mark.parametrize("columns", [(), ("x", "x"), ("",)])
def test_invalid_parquet_column_options(columns: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="nonempty and unique"):
        ParquetOptions(columns=columns)


def test_parquet_preview_preserves_temporal_nanoseconds(tmp_path: Path) -> None:
    path = tmp_path / "temporal.parquet"
    integers = pl.Series([7, None, 123456789], dtype=pl.Int64)
    table = pl.DataFrame(
        {
            "timestamp": integers.cast(pl.Datetime("ns")),
            "time": integers.cast(pl.Time),
            "duration": integers.cast(pl.Duration("ns")),
        }
    )
    table.write_parquet(path)
    imported = load_file(path)
    assert_frame_equal(imported.dataset.table, table)
    inspection = prepare_inspection(imported)
    assert inspection.first_page.rows == (
        ("1970-01-01 00:00:00.000000007", "00:00:00.000000007", "7 ns"),
        ("NULL", "NULL", "NULL"),
        ("1970-01-01 00:00:00.123456789", "00:00:00.123456789", "123456789 ns"),
    )
