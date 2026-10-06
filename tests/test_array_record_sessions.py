from pathlib import Path
from time import monotonic, sleep

import numpy as np
import pytest

from datelier.gui.editor_session import EditorSession
from datelier.gui.workspace.capture import capture_session
from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
)
from datelier.inspection.records.types import InspectSettings, RecordMode
from datelier.io.arrays.storage import ArrayStore
from datelier.io.loading import LoadPhase
from datelier.pipeline.editing import HistoryAction
from datelier.pipeline.operations import Comparison, Filter, Sort
from datelier.workspace.session_jobs import save_snapshot


def wait(editor: EditorSession) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if not editor.workspace_jobs.busy and all(
            f.loader.status.phase != LoadPhase.LOADING
            and not f.editor.busy
            and not f.arrays.busy
            and not f.record_views.pending
            for f in editor.file_sessions
        ):
            return
        sleep(0.001)
    raise AssertionError("Array record sessions did not finish")


def fixture(tmp_path: Path) -> tuple[Path, ArrayRecordMapping]:
    path = tmp_path / "records.npz"
    np.savez_compressed(
        path,
        images=np.arange(4 * 5 * 6 * 3).reshape(4, 5, 6, 3),
        labels=np.array([8, 3, 9, 5]),
        wrong=np.arange(2),
    )
    return path, ArrayRecordMapping(
        "images",
        0,
        ArrayLayout.IMAGE,
        (1, 2),
        3,
        supporting=(SupportingArray("labels", "label"),),
    )


def test_confirmed_views_share_payload_cache_without_sharing_jobs_or_rows(
    tmp_path: Path,
) -> None:
    source, mapping = fixture(tmp_path)
    original = source.read_bytes()
    editor = EditorSession()
    try:
        root = editor.new_tab(source)
        wait(editor)
        assert not root.record_views.files and root.arrays.store.temporary_path is None
        view = root.record_views.open_array(root, mapping)
        wait(editor)
        assert view.loader.active and root.loader.active
        assert view.arrays.store is root.arrays.store
        assert view.arrays.catalog is root.arrays.catalog
        # Only labels were extracted by explicit confirmation.
        assert root.arrays.store.stored_bytes < 1024
        view.editor.request(Sort(("label",)))
        wait(editor)
        view.editor.request(Filter("label", Comparison.GE, 5))
        wait(editor)
        assert view.loader.active.dataset.row_ids.to_list() == [3, 0, 2]
        assert view.arrays.catalog
        view.arrays.request(mapping.slice_settings(view.arrays.catalog, 3, channel=2))
        wait(editor)
        assert view.arrays.active
        np.testing.assert_array_equal(
            view.arrays.active.raw,
            np.arange(4 * 5 * 6 * 3).reshape(4, 5, 6, 3)[3, :, :, 2],
        )
        view.editor.request(HistoryAction.UNDO)
        wait(editor)
        assert view.loader.active.dataset.row_ids.to_list() == [1, 3, 0, 2]
        assert root.record_views.open_array(root, mapping) is view
        root.record_views.close_view(view.identity)
        assert view.closed and root.arrays.store.stored_bytes > 1024
        assert root.arrays.catalog is not None
        root.arrays.request(mapping.slice_settings(root.arrays.catalog, 1))
        wait(editor)
        assert root.arrays.active and root.arrays.active.settings.fixed[0] == 1
        assert source.read_bytes() == original
    finally:
        editor.close()


def test_deferred_named_views_resave_and_prepare_without_eager_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, mapping = fixture(tmp_path)
    workspace = tmp_path / "records.datelier"
    editor = EditorSession()
    try:
        root = editor.new_tab(source)
        wait(editor)
        view = root.record_views.open_array(root, mapping)
        wait(editor)
        view.editor.request(Sort(("label",)))
        wait(editor)
        assert view.loader.active
        view.selection.choose(view.loader.active.dataset.revision, [3])
        view_id = view.identity
        save_snapshot(workspace, capture_session(editor), False)
    finally:
        editor.close()
    original_open = ArrayStore.open_member

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("Restoration must read metadata only")

    monkeypatch.setattr(ArrayStore, "open_member", forbidden)
    reopened = EditorSession()
    try:
        reopened.open_workspace(workspace)
        wait(reopened)
        root = reopened.active
        view = root.record_views.active(root)
        assert view.identity == view_id and view.deferred and not view.recovery
        assert view.loader.active is None and view.arrays.active is None
        assert view.arrays.store is root.arrays.store
        assert root.arrays.store.temporary_path is None
        assert view.deferred.file.selection == (3,)
        save_snapshot(tmp_path / "resaved.datelier", capture_session(reopened), False)
        monkeypatch.setattr(ArrayStore, "open_member", original_open)
        reopened.prepare_records(view_id)
        wait(reopened)
        assert view.loader.active and view.deferred is None
        assert view.loader.active.dataset.row_ids.to_list() == [1, 3, 0, 2]
        assert view.selection.row_ids == {3}
        assert view.arrays.active is None
    finally:
        reopened.close()


def test_invalid_confirmation_keeps_current_records_and_cache(tmp_path: Path) -> None:
    source, mapping = fixture(tmp_path)
    editor = EditorSession()
    try:
        root = editor.new_tab(source)
        wait(editor)
        view = root.record_views.open_array(root, mapping)
        wait(editor)
        invalid = ArrayRecordMapping(
            "images",
            0,
            ArrayLayout.HEATMAP,
            (1, 2),
            supporting=(SupportingArray("wrong", "label"),),
        )
        with pytest.raises(ValueError, match="without truncation"):
            root.record_views.open_array(root, invalid)
        assert root.record_views.active_id == view.identity
        assert len(root.record_views.files) == 1 and not root.record_views.pending
        assert not view.closed
    finally:
        editor.close()


def test_sampled_inspect_focus_links_source_pixels_and_supporting_fields(
    tmp_path: Path,
) -> None:
    source, mapping = fixture(tmp_path)
    editor = EditorSession()
    try:
        root = editor.new_tab(source)
        wait(editor)
        view = root.record_views.open_array(root, mapping)
        wait(editor)
        view.editor.request(Sort(("label",)))
        wait(editor)
        view.inspect.settings = InspectSettings(
            mode=RecordMode.RANDOM, count=2, seed=19
        )
        deadline = monotonic() + 3
        while monotonic() < deadline:
            editor.poll()
            if view.inspect.jobs.active and len(view.inspect.jobs.active.row_ids) == 2:
                view.array_records.fields.get(0)
                editor.poll()
                if view.array_records.fields.get(0) is not None:
                    break
            sleep(0.001)
        records = view.inspect.jobs.active
        assert records and len(records.row_ids) == 2
        index = int(records.row_ids[0])
        assert view.array_records.source_index == index
        page = view.array_records.fields.get(0)
        assert page and page.cards[0].row_id == index
        assert next(f.text for f in page.cards[0].fields if f.name == "label") == str(
            [8, 3, 9, 5][index]
        )
        assert view.arrays.catalog
        view.arrays.request(mapping.slice_settings(view.arrays.catalog, index))
        wait(editor)
        assert view.arrays.active and view.arrays.active.settings.fixed[0] == index
    finally:
        editor.close()
