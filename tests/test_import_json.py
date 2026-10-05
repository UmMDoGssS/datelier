from pathlib import Path

import polars as pl
import pytest

from datelier.inspection import prepare_inspection
from datelier.io.importing import load_file
from datelier.io.types import ImportFailure, ImportFormat, JsonOptions


@pytest.mark.parametrize("suffix", ["json", "jsonl", "ndjson"])
def test_json_values_types_late_fields_and_preview(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"table[1].{suffix}"
    records = [
        '{"id":1,"value":1.5,"label":"café","flag":true}',
        '{"id":2,"value":null,"label":"last","late":9}',
    ]
    text = "[" + ",".join(records) + "]" if suffix == "json" else "\n".join(records)
    path.write_text(text)
    imported = load_file(path)
    assert imported.format == (
        ImportFormat.JSON if suffix == "json" else ImportFormat.JSONL
    )
    assert imported.dataset.table.schema == {
        "id": pl.Int64,
        "value": pl.Float64,
        "label": pl.String,
        "flag": pl.Boolean,
        "late": pl.Int64,
    }
    assert imported.dataset.table.rows() == [
        (1, 1.5, "café", True, None),
        (2, None, "last", None, 9),
    ]
    assert imported.dataset.row_ids.to_list() == [0, 1]
    inspection = prepare_inspection(imported)
    assert inspection.first_page.rows[1] == ("2", "NULL", "last", "NULL", "9")
    assert path.read_text() == text


@pytest.mark.parametrize("suffix", ["json", "jsonl"])
@pytest.mark.parametrize(
    "record, message",
    [
        ('{"x":{"nested":1}}', "field.*x.*nested JSON"),
        ('{"x":[1,2]}', "flatten"),
        ("1", "expected an object"),
        ('{"x":1,"x":2}', "Duplicate JSON field"),
        ('{"x":NaN}', "Nonstandard"),
        ('{"x":1e999}', "finite range"),
        ('{"x":', "Could not parse"),
    ],
)
def test_json_rejections_preserve_source(
    tmp_path: Path, suffix: str, record: str, message: str
) -> None:
    path = tmp_path / f"bad.{suffix}"
    text = f"[{record}]" if suffix == "json" else record
    path.write_text(text)
    with pytest.raises(ImportFailure, match=message):
        load_file(path)
    assert path.read_text() == text


@pytest.mark.parametrize("text", ["", "[]", "[{}]", "{}", '{"rows":[{"x":1}]}'])
def test_empty_and_wrapped_json_require_explicit_tabular_shape(
    tmp_path: Path, text: str
) -> None:
    path = tmp_path / "bad.json"
    path.write_text(text)
    with pytest.raises(ImportFailure):
        load_file(path)


def test_jsonl_blank_lines_line_numbers_and_mixed_types(tmp_path: Path) -> None:
    path = tmp_path / "table.jsonl"
    path.write_text('\n{"x":1,"y":true}\n\n{"x":"word","y":null}\n')
    imported = load_file(path, JsonOptions(read_as_text=True))
    assert imported.dataset.table.rows() == [("1", "true"), ("word", None)]
    assert imported.dataset.table.dtypes == [pl.String, pl.String]
    path.write_text('{"x":1}\n\n{"x":[]}\n')
    with pytest.raises(ImportFailure, match="Line 3"):
        load_file(path)


def test_jsonl_checks_every_record_for_nesting_and_new_fields(tmp_path: Path) -> None:
    path = tmp_path / "late.jsonl"
    path.write_text('{"x":1}\n' * 150 + '{"late":2}\n')
    table = load_file(path).dataset.table
    assert table.columns == ["x", "late"]
    assert table["late"].to_list() == [None] * 150 + [2]
    path.write_text('{"x":1}\n' * 150 + '{"late":{"hidden":2}}\n')
    with pytest.raises(ImportFailure, match="Line 151.*late"):
        load_file(path)


@pytest.mark.parametrize("suffix", ["json", "jsonl"])
def test_batches_preserve_empty_rows_late_fields_and_type_changes(
    tmp_path: Path, suffix: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    import datelier.io.json_records as arrays
    import datelier.io.records as batches

    monkeypatch.setattr(batches, "BATCH_RECORDS", 2)
    monkeypatch.setattr(batches, "BLOCK_BATCHES", 2)
    monkeypatch.setattr(arrays, "CHUNK_CHARACTERS", 7)
    rows = [
        {},
        {},
        {"x": 1, "label": 'café "quote"\nline'},
        {},
        {"x": 2.5, "late": True},
        {},
    ]
    path = tmp_path / ("batch." + suffix)
    path.write_text(
        json.dumps(rows, ensure_ascii=False)
        if suffix == "json"
        else "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    )
    imported = load_file(path)
    assert imported.dataset.table.schema == {
        "x": pl.Float64,
        "label": pl.String,
        "late": pl.Boolean,
    }
    assert imported.dataset.table.rows() == [
        (None, None, None),
        (None, None, None),
        (1.0, 'café "quote"\nline', None),
        (None, None, None),
        (2.5, None, True),
        (None, None, None),
    ]
    assert imported.dataset.row_ids.to_list() == list(range(6))
    assert load_file(path, JsonOptions(read_as_text=True)).dataset.table.row(4) == (
        "2.5",
        None,
        "true",
    )


@pytest.mark.parametrize(
    "text",
    [
        '[{"x":1},]',
        '[{"x":1}{"x":2}]',
        '[{"x":1}]extra',
        '[{"x":1}',
        '[{"x":"unterminated}]',
        '[{"x":1},\n',
    ],
)
def test_streaming_json_rejects_bad_array_grammar(
    tmp_path: Path, text: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import datelier.io.json_records as arrays

    monkeypatch.setattr(arrays, "CHUNK_CHARACTERS", 3)
    path = tmp_path / "bad.json"
    path.write_text(text)
    with pytest.raises(ImportFailure):
        load_file(path)
    assert path.read_text() == text
