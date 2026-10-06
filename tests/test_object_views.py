from pathlib import Path
from threading import Event
from time import monotonic, sleep

import polars as pl
import pytest

from datelier.gui.editor_session import EditorSession
from datelier.gui.workspace.capture import capture_session
from datelier.inspection.objects.types import ObjectNode
from datelier.io.loading import LoadPhase
from datelier.io.types import ImportFormat
from datelier.pipeline.editing import HistoryAction
from datelier.pipeline.operations import Sort
from datelier.workspace.session_jobs import save_snapshot


def wait(editor: EditorSession) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        files = tuple(
            f for owner in editor.files for f in (owner, *owner.record_views.files)
        )
        if not editor.workspace_jobs.busy and all(
            f.loader.status.phase != LoadPhase.LOADING
            and not f.editor.busy
            and not f.record_views.pending
            for f in files
        ):
            return
        sleep(0.001)
    raise AssertionError("Object view work did not complete")


def fixture_source(tmp_path: Path) -> Path:
    path = tmp_path / "nested.json"
    path.write_text(
        '{"train":[{"id":8,"x":3.5},{"id":3,"x":1.5}],'
        '"test":[{"id":2,"x":9.5}],"invalid":[{"x":[]}]}'
    )
    return path


def test_named_views_preserve_other_nodes_histories_and_identity(
    tmp_path: Path,
) -> None:
    source = fixture_source(tmp_path)
    before = source.read_bytes()
    editor = EditorSession(initial_path=source)
    root = editor.active
    try:
        root.loader.request(source)
        wait(editor)
        assert (
            root.loader.active
            and root.loader.active.imported.format == ImportFormat.OBJECT
        )
        original = root.loader.active.imported.object_root
        train = root.record_views.open(root, ("train",))
        test = root.record_views.open(root, ("test",))
        wait(editor)
        assert train.loader.active and test.loader.active
        assert train.loader.active.imported.object_root is original
        assert train.loader.active.dataset.row_ids.to_list() == [0, 1]
        assert test.loader.active.dataset.row_ids.to_list() == [0]
        train.editor.request(Sort(("x",)))
        wait(editor)
        train.selection.choose(train.loader.active.dataset.revision, [1])
        test.selection.choose(test.loader.active.dataset.revision, [0])
        assert train.loader.active.dataset.row_ids.to_list() == [1, 0]
        assert test.loader.active.dataset.table["x"].to_list() == [9.5]
        assert root.loader.active.imported.object_root is original
        assert root.record_views.open(root, ("train",)) is train
        failed = root.record_views.open(root, ("invalid",))
        wait(editor)
        assert failed.closed and root.record_views.active_id == train.identity
        assert "nested" in root.record_views.message
        assert len(root.record_views.files) == 2
        assert train.selection.row_ids == {1} and test.selection.row_ids == {0}
        train.editor.request(HistoryAction.UNDO)
        wait(editor)
        assert train.loader.active.dataset.row_ids.to_list() == [0, 1]
        assert source.read_bytes() == before
    finally:
        editor.close()


def test_named_views_and_node_navigation_reopen_with_session(tmp_path: Path) -> None:
    source = fixture_source(tmp_path)
    workspace = tmp_path / "session.datelier"
    editor = EditorSession(initial_path=source)
    try:
        root = editor.active
        root.loader.request(source)
        wait(editor)
        view = root.record_views.open(root, ("train",))
        wait(editor)
        assert view.loader.active
        view.editor.request(Sort(("x",)))
        wait(editor)
        view.selection.choose(view.loader.active.dataset.revision, [1])
        root.record_views.path = ("train", 0, "x")
        root.record_views.expanded = {(), ("train",)}
        root.record_views.focus_path = ("train",)
        root_id, view_id = root.identity, view.identity
        save_snapshot(workspace, capture_session(editor), False)
    finally:
        editor.close()
    restored = EditorSession()
    try:
        restored.open_workspace(workspace)
        wait(restored)
        root = restored.active
        assert root.identity == root_id
        assert root.record_views.active_id == view_id
        assert root.record_views.path == ("train", 0, "x")
        assert root.record_views.focus_path == ("train",)
        view = root.record_views.active(root)
        assert view.view_name == "$['train']"
        assert view.loader.active and view.editor.pipeline
        assert view.loader.active.dataset.row_ids.to_list() == [1, 0]
        assert view.selection.row_ids == {1}
        assert view.editor.pipeline.can_undo
        assert not view.analysis.jobs.results
        assert root.loader.active and root.loader.active.imported.object_root
        assert root.loader.active.imported.object_root.at(("test", 0, "x")).value == 9.5
        assert (
            view.loader.active.imported.object_root
            is root.loader.active.imported.object_root
        )
    finally:
        restored.close()


def test_closing_source_abandons_extraction_without_sibling_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import datelier.io.objects as objects

    source = fixture_source(tmp_path)
    editor = EditorSession()
    started, release = Event(), Event()
    original = objects.extract_records

    def slow(node: ObjectNode, *, as_text: bool = False) -> pl.DataFrame:
        started.set()
        assert release.wait(5)
        return original(node, as_text=as_text)

    try:
        root = editor.new_tab(source)
        sibling = editor.new_tab(source)
        wait(editor)
        monkeypatch.setattr(objects, "extract_records", slow)
        view = root.record_views.open(root, ("train",))
        assert started.wait(2)
        editor.close_tab(root.identity)
        release.set()
        wait(editor)
        assert view.closed and view.loader.active is None
        assert not sibling.record_views.files
        assert sibling.loader.active and sibling.loader.active.imported.object_root
    finally:
        release.set()
        editor.close()


def test_missing_source_relinks_owner_and_its_named_views(tmp_path: Path) -> None:
    source = fixture_source(tmp_path)
    replacement = tmp_path / "replacement.json"
    workspace = tmp_path / "session.datelier"
    editor = EditorSession()
    try:
        root = editor.new_tab(source)
        other_path = tmp_path / "other.csv"
        other_path.write_text("x\n1\n")
        editor.new_tab(other_path)
        wait(editor)
        root.record_views.open(root, ("train",))
        wait(editor)
        owner_id = root.identity
        save_snapshot(workspace, capture_session(editor), False)
    finally:
        editor.close()
    source.rename(replacement)
    restored = EditorSession()
    try:
        restored.open_workspace(workspace)
        wait(restored)
        root = next(f for f in restored.files if f.identity == owner_id)
        assert root.recovery and restored.active.loader.active
        restored.recover_source(owner_id, relink=replacement)
        wait(restored)
        assert root.recovery is None and root.loader.active
        view = root.record_views.files[0]
        assert (
            view.loader.active and view.loader.active.dataset.source.path == replacement
        )
        assert view.loader.active.dataset.row_ids.to_list() == [0, 1]
        assert (
            view.loader.active.imported.object_root
            is root.loader.active.imported.object_root
        )
        save_snapshot(tmp_path / "relinked.datelier", capture_session(restored), False)
    finally:
        restored.close()
