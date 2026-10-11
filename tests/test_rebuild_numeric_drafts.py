"""Explicit numeric drafts preserve metadata laziness, exact values and provenance."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from test_rebuild_sources import until

from datelier.application.sessions import EditorController
from datelier.application.sessions.workspace import capture_session
from datelier.io.types import ArrayOptions
from datelier.pipeline.operations import Sort
from datelier.workspace.sessions.jobs import save_snapshot


def test_supports_project_other_axes_and_structured_fields_without_truncation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "records.npz"
    labels = np.array(
        [(30, "three"), (10, "one"), (20, "two")], dtype=[("id", "i8"), ("name", "U8")]
    )
    values = np.arange(60).reshape(3, 4, 5)
    np.savez_compressed(
        source, values=values, scores=np.arange(6).reshape(2, 3), labels=labels
    )
    original = source.read_bytes()
    editor = EditorController()
    try:
        file = editor.active
        file.open(source, ArrayOptions(record_table=False))
        until(editor, lambda: file.arrays.catalog is not None)
        model = file.array_source
        model.choose("values")
        draft = model.mapping
        assert draft
        draft.candidate = ("scores",)
        score = draft.add()
        score.column, score.record_axis, score.fixed = "score", 1, "1,0"
        draft.candidate = ("labels",)
        label, name = draft.add(), draft.add()
        label.column, label.field = "label", "id"
        name.column, name.field = "name", "name"
        assert name.key != label.key
        mapping = draft.build()
        assert file.arrays.active is None and file.arrays.store.temporary_path is None
        score.fixed = "2,0"
        with pytest.raises(ValueError, match="coordinates"):
            draft.build()
        score.fixed = "1,0"
        name.column = "label"
        with pytest.raises(ValueError, match="distinct"):
            draft.build()
        name.column = "name"
        file.record_views.open_array(file, mapping)
        until(editor, lambda: bool(file.record_views.files))
        view = editor.current
        assert view.inspection
        assert view.inspection.dataset.table["score"].to_list() == [3, 4, 5]
        assert view.inspection.dataset.table["name"].to_list() == [
            "three",
            "one",
            "two",
        ]
        view.editor.request(Sort(("label",)))
        until(editor, lambda: not view.editor.busy)
        assert view.inspection.dataset.row_ids.to_list() == [1, 2, 0]
        view.array_records.bind_record("record_index", 1)
        view.array_record_source.request()
        until(editor, lambda: view.array_records.jobs.active is not None)
        prepared = view.array_records.jobs.active
        assert prepared
        np.testing.assert_array_equal(prepared.raw, values[1])
        assert source.read_bytes() == original
    finally:
        editor.close()


def test_bad_slice_never_starts_work_and_per_member_drafts_survive_navigation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "complex.npz"
    values = np.arange(60).reshape(3, 4, 5).astype(complex) + 7j
    np.savez_compressed(source, values=values, scalar=np.array(123))
    editor = EditorController()
    try:
        file = editor.active
        file.open(source, ArrayOptions(record_table=False))
        until(editor, lambda: file.arrays.catalog is not None)
        model = file.array_source
        model.choose("values")
        draft = model.slice
        draft.axes, draft.fixed, draft.starts, draft.counts = (
            "2,0",
            "0,2,0",
            "1,0",
            "3,2",
        )
        draft.manual, draft.low, draft.high, draft.component = True, 9, 2, "Imaginary"
        with pytest.raises(ValueError, match="range"):
            model.request()
        assert not file.arrays.busy and file.arrays.store.temporary_path is None
        draft.low, draft.high = 2, 9
        draft.starts = "5,0"
        with pytest.raises(ValueError, match="Window start"):
            model.request()
        model.choose("scalar")
        model.request()
        until(editor, lambda: file.arrays.active is not None)
        assert file.arrays.active and file.arrays.active.raw.item() == 123
        model.choose("values")
        assert model.slice is draft and draft.starts == "5,0"
        draft.starts = "1,0"
        model.request()
        until(editor, lambda: not file.arrays.busy)
        prepared = file.arrays.active
        assert prepared and prepared.settings.component == "Imaginary"
        np.testing.assert_array_equal(prepared.raw, values[:2, 2, 1:4].T)
        np.testing.assert_array_equal(prepared.numeric, np.full((3, 2), 7.0))
        assert not prepared.raw.flags.writeable
    finally:
        editor.close()


def test_unprepared_slice_draft_and_confirmed_mapping_restore_without_decoding(
    tmp_path: Path,
) -> None:
    source, workspace = tmp_path / "records.npz", tmp_path / "session.json"
    np.savez_compressed(
        source, values=np.arange(60).reshape(3, 4, 5), labels=np.array([3, 1, 2])
    )
    editor = EditorController()
    try:
        file = editor.active
        file.open(source, ArrayOptions(record_table=False))
        until(editor, lambda: file.arrays.catalog is not None)
        model = file.array_source
        model.choose("values")
        mapping = model.mapping
        assert mapping
        mapping.candidate = ("labels",)
        support = mapping.add()
        support.column = "priority"
        file.record_views.open_array(file, mapping.build())
        until(editor, lambda: bool(file.record_views.files))
        model.slice.axes, model.slice.fixed = "2,0", "0,2,0"
        model.slice.starts, model.slice.counts = "1,0", "3,2"
        model.slice.manual, model.slice.low, model.slice.high = True, 1, 40
        save_snapshot(workspace, capture_session(editor), False)
        assert file.arrays.active is None
    finally:
        editor.close()
    reopened = EditorController()
    try:
        reopened.open_workspace(workspace)
        until(reopened, lambda: not reopened.workspace.busy)
        file = reopened.active
        settings = file.array_source.capture_slice()
        assert settings.axes == (2, 0) and settings.value_range == (1, 40)
        assert settings.fixed == (0, 2, 0) and settings.starts == (1, 0)
        view = file.record_views.files[0]
        assert view.recovery and view.recovery.deferred
        recipe = view.recovery.file.recipe
        assert recipe and isinstance(recipe.options, ArrayOptions)
        assert recipe.options.mapping
        assert recipe.options.mapping.supporting[0].column == "priority"
        assert file.arrays.active is None and view.array_records.jobs.active is None
        assert file.arrays.store.temporary_path is None
    finally:
        reopened.close()


def test_record_rebinding_changes_only_provenance_coordinates(tmp_path: Path) -> None:
    source = tmp_path / "records.npy"
    np.save(source, np.arange(60).reshape(3, 4, 5))
    editor = EditorController()
    try:
        file = editor.active
        file.open(source)
        until(editor, lambda: file.arrays.catalog is not None)
        record = file.array_record_source
        base = replace(record.settings, axes=(1, 2), fixed=(0, 0, 0))
        record.settings = base
        record.slice.starts, record.slice.counts = "1,2", "2,3"
        record.slice.manual, record.slice.low, record.slice.high = True, 0, 99
        record.jobs.settings = replace(base, fixed=(2, 0, 0))
        record.sync(file.arrays.catalog)
        assert record.slice.fixed == "2,0,0"
        assert record.slice.starts == "1,2" and record.slice.high == 99
    finally:
        editor.close()
