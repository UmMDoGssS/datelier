from pathlib import Path

import pytest

from datelier.inspection.objects.types import node_label
from datelier.io.importing import load_file
from datelier.io.types import ImportFailure, ImportFormat, JsonOptions, ObjectOptions
from datelier.workspace.codec import decode_record, encode
from datelier.workspace.restore import restore_recipe
from datelier.workspace.storage import reference_source
from datelier.workspace.types import Workspace


def test_preserved_json_hierarchy_and_record_provenance(tmp_path: Path) -> None:
    path = tmp_path / "nested.json"
    content = '{"a/b":{"~rows":[{"id":7,"x":1.5},{"id":3}]},"scalar":true}'
    path.write_text(content)
    root = load_file(path, ObjectOptions(), format=ImportFormat.OBJECT)
    assert root.object_root is not None
    assert root.object_root.at(("scalar",)).value is True
    assert root.object_root.at(("a/b", "~rows", 1, "id")).value == 3
    options = ObjectOptions(node_path=("a/b", "~rows"))
    imported = load_file(path, options, format=ImportFormat.OBJECT)
    assert imported.dataset.table.rows() == [(7, 1.5), (3, None)]
    assert imported.dataset.row_ids.to_list() == [0, 1]
    assert imported.object_root == root.object_root
    assert node_label(options.node_path or ()) == "$['a/b']['~rows']"
    recipe = Workspace(
        reference_source(imported.dataset.source), imported.format, options
    )
    restored = restore_recipe(decode_record(Workspace, encode(recipe)))
    assert restored.inspection.dataset.table.rows() == imported.dataset.table.rows()
    assert restored.inspection.imported.object_root == root.object_root
    assert path.read_text() == content


@pytest.mark.parametrize(
    "content", ["null", "42", '"hello"', "[]", "{}", '[1,{"a":[]}]']
)
def test_scalar_empty_and_mixed_objects_are_browsable(
    tmp_path: Path, content: str
) -> None:
    path = tmp_path / "any.json"
    path.write_text(content)
    imported = load_file(path, ObjectOptions(), format=ImportFormat.OBJECT)
    assert imported.object_root is not None
    assert imported.dataset.table.height == 1
    assert path.read_text() == content


def test_toml_types_preserved_and_dates_losslessly_extracted(tmp_path: Path) -> None:
    from datetime import date, datetime, time

    path = tmp_path / "config.toml"
    content = 'name = "café"\n[[records]]\nday = 2026-10-06\nat = 10:20:30.123456\n'
    content += "stamp = 2026-10-06T10:20:30+07:00\nvalue = 1.5\n"
    path.write_text(content)
    imported = load_file(path)
    assert imported.format == ImportFormat.OBJECT and imported.object_root is not None
    record = imported.object_root.at(("records", 0))
    assert type(record.at(("day",)).value) is date
    assert type(record.at(("at",)).value) is time
    assert type(record.at(("stamp",)).value) is datetime
    table = load_file(path, ObjectOptions(node_path=("records",))).dataset.table
    assert table.row(0) == (
        "2026-10-06",
        "10:20:30.123456",
        "2026-10-06T10:20:30+07:00",
        1.5,
    )
    assert path.read_text() == content


@pytest.mark.parametrize(
    "content", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}', "{", "[]more"]
)
def test_malformed_json_has_local_diagnostic(tmp_path: Path, content: str) -> None:
    path = tmp_path / "bad.json"
    path.write_text(content)
    with pytest.raises(ImportFailure):
        load_file(path, ObjectOptions(), format=ImportFormat.OBJECT)
    assert path.read_text() == content


@pytest.mark.parametrize(
    "content,path_to_node",
    [
        ('{"rows":[1,{}]}', ("rows",)),
        ('{"rows":[]}', ("rows",)),
        ('{"rows":[{}]}', ("rows",)),
        ('{"rows":[{"x":1}]}', ("absent",)),
        ('{"rows":[{"x":1}]}', ("rows", 9)),
        ('{"rows":[{"x":1}]}', ("rows", 0)),
    ],
)
def test_incompatible_record_nodes_do_not_flatten(
    tmp_path: Path, content: str, path_to_node: tuple[str | int, ...]
) -> None:
    path = tmp_path / "mixed.json"
    path.write_text(content)
    with pytest.raises(ImportFailure):
        load_file(
            path, ObjectOptions(node_path=path_to_node), format=ImportFormat.OBJECT
        )
    assert (
        load_file(path, ObjectOptions(), format=ImportFormat.OBJECT).object_root
        is not None
    )
    assert path.read_text() == content


def test_flat_json_import_retained_and_mixed_text_is_explicit(tmp_path: Path) -> None:
    path = tmp_path / "flat.json"
    path.write_text('[{"id":1,"x":true},{"id":2,"x":"hello"}]')
    legacy = load_file(path, JsonOptions(read_as_text=True))
    object_view = load_file(
        path, ObjectOptions(node_path=(), read_as_text=True), format=ImportFormat.OBJECT
    )
    assert object_view.dataset.table.rows() == legacy.dataset.table.rows()
    assert legacy.object_root is None


def test_toml_nonfinite_and_malformed_values(tmp_path: Path) -> None:
    import math

    path = tmp_path / "numbers.toml"
    path.write_text("[[rows]]\nx = nan\ny = +inf\n")
    imported = load_file(path, ObjectOptions(node_path=("rows",)))
    x, y = imported.dataset.table.row(0)
    assert math.isnan(x) and y == math.inf
    path.write_text("x = 1\nx = 2\n")
    with pytest.raises(ImportFailure, match="Could not parse"):
        load_file(path)
