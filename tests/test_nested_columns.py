import json
from dataclasses import replace
from pathlib import Path

import polars as pl
import pytest

from datelier.inspection.records import InspectSettings
from datelier.inspection.records.prepare import prepare_record_page, prepare_records
from datelier.inspection.table import prepare_inspection
from datelier.io.importing import load_file, load_inspectable_file
from datelier.io.types import ImportFailure, ImportFormat, JsonOptions, ObjectOptions
from datelier.pipeline import Pipeline, Sort
from datelier.workspace.recipes.codec import decode_record, encode
from datelier.workspace.single import Workspace
from datelier.workspace.single.restore import restore_recipe
from datelier.workspace.single.storage import reference_source


@pytest.mark.parametrize("suffix", ["json", "jsonl"])
def test_nested_batches_preserve_null_empty_late_fields_and_types(
    tmp_path: Path, suffix: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datelier.io.tabular import records

    monkeypatch.setattr(records, "BATCH_RECORDS", 1)
    monkeypatch.setattr(records, "BLOCK_BATCHES", 2)
    rows = [
        {"id": 0, "obj": None, "xs": None},
        {"id": 1, "obj": {}, "xs": []},
        {"id": 2, "obj": {"x": 1}, "xs": [1, None, 2]},
        {"id": 3, "obj": {"late": {"a": [3]}}, "xs": [3.5]},
    ]
    path = tmp_path / f"nested.{suffix}"
    content = json.dumps(rows) if suffix == "json" else "\n".join(map(json.dumps, rows))
    path.write_text(content)
    imported = load_inspectable_file(path)
    table = imported.dataset.table
    assert isinstance(table.schema["obj"], pl.Struct)
    assert table.schema["xs"] == pl.List(pl.Float64)
    assert table["obj"].to_list() == [
        None,
        {"x": None, "late": None},
        {"x": 1, "late": None},
        {"x": None, "late": {"a": [3]}},
    ]
    assert table["xs"].to_list() == [None, [], [1.0, None, 2.0], [3.5]]
    assert imported.dataset.row_ids.to_list() == [0, 1, 2, 3]
    page = prepare_inspection(imported).first_page
    assert page.rows[0] == ("0", "NULL", "NULL")
    assert page.rows[1] == ("1", "{ ... }", "[ ... ] (0 items)")
    assert page.rows[2] == ("2", "{ ... }", "[ ... ] (3 items)")
    text = load_file(path, JsonOptions(read_as_text=True)).dataset.table
    assert text.schema["obj"] == pl.String
    assert json.loads(text["obj"][3]) == {"late": {"a": [3]}}
    assert path.read_text() == content


def test_object_record_views_include_nested_containers(tmp_path: Path) -> None:
    path = tmp_path / "wrapped.json"
    rows = [{"id": 1, "obj": {"child": {"hello": "世界"}}, "xs": [[1, 2], [3]]}]
    content = json.dumps({"rows": rows}, ensure_ascii=False)
    path.write_text(content)
    options = ObjectOptions(node_path=("rows",))
    imported = load_file(path, options, format=ImportFormat.OBJECT)
    assert imported.dataset.table.to_dicts() == rows
    assert imported.object_root is not None
    assert imported.object_root.at(("rows", 0, "xs", 1, 0)).value == 3
    assert path.read_text() == content


def test_complete_nested_inspect_values_keep_sorted_record_identity_and_restore(
    tmp_path: Path,
) -> None:
    path = tmp_path / "records.json"
    rows = [
        {"id": 2, "obj": {"text": "中" * 6000}, "xs": [[1, None], [2, 3]]},
        {"id": 1, "obj": {"text": "last"}, "xs": []},
    ]
    content = json.dumps(rows, ensure_ascii=False)
    path.write_text(content)
    imported = load_file(path)
    pipeline = Pipeline.start(imported.dataset).apply(Sort(("id",)))
    dataset = pipeline.current
    settings = InspectSettings(primary="obj", supporting=("id", "xs"), gallery=False)
    cards = prepare_record_page(dataset, prepare_records(dataset, settings), 0).cards
    assert [c.row_id for c in cards] == [1, 0]
    primary = cards[1].primary
    assert primary is not None and primary.lines is not None
    assert not primary.truncated and json.loads(primary.text) == rows[0]["obj"]
    assert cards[1].fields[1].text == "[ ... ]"
    list_settings = replace(settings, primary="xs")
    card = prepare_record_page(
        dataset, prepare_records(dataset, list_settings), 0
    ).cards[1]
    assert card.primary is not None and json.loads(card.primary.text) == rows[0]["xs"]
    assert card.fields[1].text == "[ ... ]" and card.fields[1].lines is None
    recipe = Workspace(
        reference_source(imported.dataset.source),
        imported.format,
        imported.options,
        history=pipeline.history,
        cursor=pipeline.cursor,
    )
    restored = restore_recipe(decode_record(Workspace, encode(recipe)))
    assert restored.inspection.dataset.table.equals(dataset.table)
    assert restored.inspection.dataset.row_ids.equals(dataset.row_ids)
    assert path.read_text() == content


@pytest.mark.parametrize(
    "content", ['[{"xs":[{"x":NaN}]}]', '[{"xs":[1e999]}]', '[{"obj":{"x":1,"x":2}}]']
)
def test_nested_invalid_json_cannot_hide_invalid_values(
    tmp_path: Path, content: str
) -> None:
    path = tmp_path / "bad.json"
    path.write_text(content)
    with pytest.raises(ImportFailure):
        load_file(path)
    assert path.read_text() == content
