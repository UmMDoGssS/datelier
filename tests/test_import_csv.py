import os
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from datelier.io.tabular.csv import CsvOptions, ImportFailure, load_csv


def write_csv(tmp_path: Path, content: bytes) -> Path:
    path = tmp_path / "sample[1].csv"
    path.write_bytes(content)
    return path


def test_csv_values_types_identity_and_source_preservation(tmp_path: Path) -> None:
    content = b'row_id,amount,label\n9,1.5,"hello, world"\n3,,caf\xc3\xa9\n'
    path = write_csv(tmp_path, content)
    imported = load_csv(path)
    table = imported.dataset.table
    assert table.schema == {
        "row_id": pl.Int64,
        "amount": pl.Float64,
        "label": pl.String,
    }
    assert table.rows() == [(9, 1.5, "hello, world"), (3, None, "café")]
    assert imported.dataset.row_ids.to_list() == [0, 1]
    assert imported.dataset.source.path == path.resolve()
    assert imported.options == CsvOptions()
    assert path.read_bytes() == content


def test_options_dates_nulls_skip_rows_and_multiline_quotes(tmp_path: Path) -> None:
    path = write_csv(tmp_path, b"skip me\n2026-10-04;'two\nlines';NA\n")
    imported = load_csv(
        path,
        CsvOptions(
            separator=";",
            has_header=False,
            quote_char="'",
            null_values=("NA",),
            try_parse_dates=True,
            skip_rows=1,
        ),
    )
    assert imported.dataset.table.row(0) == (date(2026, 10, 4), "two\nlines", None)
    assert imported.dataset.table.columns == ["column_1", "column_2", "column_3"]


def test_mixed_types_and_inference_window_have_defined_outcomes(tmp_path: Path) -> None:
    path = write_csv(tmp_path, b"mixed,short\n1,yes\nword\n")
    assert load_csv(path).dataset.table.rows() == [("1", "yes"), ("word", None)]
    with pytest.raises(ImportFailure, match="infer all rows"):
        load_csv(path, CsvOptions(infer_schema_length=1))
    assert (
        load_csv(path, CsvOptions(infer_schema_length=None)).dataset.table.height == 2
    )
    strings = load_csv(path, CsvOptions(infer_types=False))
    assert all(dtype == pl.String for dtype in strings.dataset.table.dtypes)
    assert "text" in strings.diagnostics[0]


def test_header_only_and_duplicate_headers(tmp_path: Path) -> None:
    path = write_csv(tmp_path, b"a,a\n")
    imported = load_csv(path)
    assert imported.dataset.table.columns == ["a", "a_duplicated_0"]
    assert imported.dataset.table.height == 0
    assert imported.dataset.row_ids.to_list() == []
    assert "no data rows" in imported.diagnostics[0]


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"a,b\n1,2,3\n",
        b'a\n"unterminated\n',
        b"a\n\xff\n",
        b"bad\xff\n1\n",
        b"bad\xff",
    ],
)
def test_invalid_csv_fails_without_modifying_source(
    tmp_path: Path, content: bytes
) -> None:
    path = write_csv(tmp_path, content)
    with pytest.raises(ImportFailure, match="sample"):
        load_csv(path)
    assert path.read_bytes() == content


def test_missing_source_has_useful_message(tmp_path: Path) -> None:
    with pytest.raises(ImportFailure, match="Could not read source"):
        load_csv(tmp_path / "missing.csv")


def test_changed_source_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write_csv(tmp_path, b"a\n1\n")
    original_stat = Path.stat
    calls = 0

    def changed_stat(target: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        nonlocal calls
        if target == path:
            calls += 1
            if calls == 2:
                # Simulate an external writer after parsing and before publication.
                path.write_bytes(b"a\n1\n2\n")
        return original_stat(target, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "stat", changed_stat)
    with pytest.raises(ImportFailure, match="changed during import"):
        load_csv(path)


@pytest.mark.parametrize(
    "options",
    [
        {"separator": ""},
        {"separator": "é"},
        {"quote_char": "\n"},
        {"infer_schema_length": 0},
        {"skip_rows": -1},
    ],
)
def test_invalid_options(options: dict[str, str | int]) -> None:
    # Separate calls keep the public option types checked rather than hiding
    # an intentionally heterogeneous argument dictionary behind Any.
    with pytest.raises(ValueError):
        if "separator" in options:
            value = options["separator"]
            assert isinstance(value, str)
            CsvOptions(separator=value)
        elif "quote_char" in options:
            value = options["quote_char"]
            assert isinstance(value, str)
            CsvOptions(quote_char=value)
        elif "infer_schema_length" in options:
            value = options["infer_schema_length"]
            assert isinstance(value, int)
            CsvOptions(infer_schema_length=value)
        else:
            value = options["skip_rows"]
            assert isinstance(value, int)
            CsvOptions(skip_rows=value)
