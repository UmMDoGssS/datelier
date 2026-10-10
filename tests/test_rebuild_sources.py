"""Fresh object/array controllers preserve explicit preparation and row provenance."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

import numpy as np
import pytest

from datelier.application.editor import EditorController
from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    SupportingArray,
)
from datelier.io.types import ArrayOptions, ImportFormat, ObjectOptions
from datelier.pipeline.operations import Sort


def until(editor: EditorController, condition: Callable[[], bool]) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if condition():
            return
        sleep(0.001)
    raise AssertionError("Source preparation timed out")


def test_hierarchy_extracts_independent_typed_records_and_full_scalar_pages(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.json"
    text = "中é" * 3000
    import json

    source.write_text(json.dumps({"long": text, "rows": [{"x": 3}, {"x": 1}]}))
    original = source.read_bytes()
    editor = EditorController()
    try:
        root = editor.active
        root.open(source, ObjectOptions(), format=ImportFormat.OBJECT)
        until(editor, lambda: root.objects.root is not None)
        assert {entry.label for entry in root.objects.entries} == {"'long'", "'rows'"}
        root.objects.choose(("long",))
        editor.poll()
        assert root.objects.length == len(text) and root.objects.detail == text[:4096]
        root.objects.page(1)
        editor.poll()
        assert root.objects.detail == text[4096:8192]
        root.objects.choose(("rows",))
        root.record_views.open(root, ("rows",))
        until(editor, lambda: bool(root.record_views.files))
        view = root.record_views.files[0]
        assert editor.current is view and view.inspection
        assert view.inspection.dataset.table["x"].to_list() == [3, 1]
        view.editor.request(Sort(("x",)))
        until(editor, lambda: not view.editor.busy)
        assert view.inspection.dataset.row_ids.to_list() == [1, 0]
        assert root.inspection and root.inspection.imported.options == ObjectOptions()
        root.record_views.close_view(view.identity)
        assert editor.current is root and view.closed
        assert source.read_bytes() == original
    finally:
        editor.close()


def test_generic_record_slice_keeps_source_index_after_sort_and_sibling_close(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.npz"
    values = np.arange(24).reshape(3, 2, 4)
    np.savez_compressed(
        source, values=values, labels=np.array([3, 1, 2]), wrong=np.arange(2)
    )
    original = source.read_bytes()
    editor = EditorController()
    try:
        root = editor.active
        root.open(source, ArrayOptions(record_table=False))
        until(editor, lambda: root.arrays.catalog is not None)
        assert root.arrays.active is None and root.arrays.store.temporary_path is None
        model = root.array_source
        model.choose("values")
        assert model.mapping_reason and model.support_choices == ("labels", "wrong")
        model.mapping = replace(model.mapping, layout=ArrayLayout.GENERIC)
        model.supporting = ("wrong",)
        with pytest.raises(ValueError, match="do not match"):
            model.confirmed_mapping()
        model.supporting = ("labels",)
        mapping = model.confirmed_mapping()
        assert mapping.supporting == (SupportingArray("labels", "labels"),)
        root.record_views.open_array(root, mapping)
        until(editor, lambda: bool(root.record_views.files))
        view = root.record_views.files[0]
        assert view.inspection
        view.editor.request(Sort(("labels",)))
        until(editor, lambda: not view.editor.busy)
        assert view.inspection.dataset.row_ids.to_list() == [1, 2, 0]
        view.array_records.bind_record("payload", 1)
        # The mapped payload column is preserved by the import recipe.
        column = view.records.settings.primary
        assert column
        view.array_records.bind_record(column, 1)
        view.array_record_source.request()
        until(editor, lambda: view.array_records.jobs.active is not None)
        prepared = view.array_records.jobs.active
        assert prepared and prepared.settings.fixed[0] == 1
        np.testing.assert_array_equal(prepared.raw, values[1])
        view.array_records.bind_record(column, 2)
        assert view.array_records.jobs.active is None
        assert view.array_records.jobs.settings.fixed[0] == 2
        root.record_views.close_view(view.identity)
        assert view.closed and root.arrays.catalog
        model.choose("values")
        model.request()
        until(editor, lambda: root.arrays.active is not None)
        assert root.arrays.active and source.read_bytes() == original
    finally:
        editor.close()


def test_saved_numeric_views_restore_drafts_without_decoding(tmp_path: Path) -> None:
    from datelier.application.workspace import capture_session
    from datelier.inspection.arrays.settings import SliceSettings
    from datelier.workspace.session_jobs import save_snapshot

    source, workspace = tmp_path / "arrays.npz", tmp_path / "session.json"
    np.savez_compressed(source, cube=np.arange(60).reshape(3, 4, 5), wrong=np.arange(2))
    editor = EditorController()
    try:
        file = editor.active
        file.open(source)
        until(editor, lambda: file.arrays.catalog is not None)
        file.array_source.choose("cube")
        file.array_source.settings = SliceSettings(
            "cube", (2, 0), (0, 2, 0), (1, 0), (3, 2)
        )
        file.array_source.height = 340
        file.array_record_source.height = 310
        file.array_source.member_mode = False
        file.array_records.jobs.settings = SliceSettings("cube", (1, 2), (1, 0, 0))
        save_snapshot(workspace, capture_session(editor), False)
    finally:
        editor.close()
    reopened = EditorController()
    try:
        reopened.open_workspace(workspace)
        until(reopened, lambda: not reopened.workspace.busy)
        file = reopened.active
        assert (
            file.array_source.height == 340 and file.array_record_source.height == 310
        )
        assert not file.array_source.member_mode
        assert file.array_source.settings.axes == (2, 0)
        assert file.array_records.jobs.settings.fixed == (1, 0, 0)
        assert file.arrays.active is None and file.array_records.jobs.active is None
        assert file.arrays.store.temporary_path is None
    finally:
        reopened.close()
