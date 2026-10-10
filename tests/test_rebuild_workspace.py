"""Whole-session restoration and partial recovery against GUI-free controllers."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

from datelier.application.editor import EditorController
from datelier.application.workspace import capture_session
from datelier.pipeline.operations import Sort
from datelier.workspace.session_storage import read_session_workspace


def until(editor: EditorController, condition: Callable[[], bool]) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if condition():
            return
        sleep(0.002)
    raise AssertionError(editor.workspace.message)


def test_session_independent_recipes_recovery_and_no_implicit_work(
    tmp_path: Path,
) -> None:
    first_path, second_path = tmp_path / "first.csv", tmp_path / "second.csv"
    first_path.write_bytes(b"x,y\n3,1\n1,2\n2,3\n")
    second_path.write_bytes(b"x,y\n7,9\n8,6\n")
    workspace = tmp_path / "session.json"
    editor = EditorController()
    try:
        first = editor.active
        first.open(first_path)
        second = editor.new_file(second_path)
        until(
            editor,
            lambda: first.inspection is not None and second.inspection is not None,
        )
        first.editor.request(Sort(("x",)))
        until(editor, lambda: not first.editor.busy)
        assert first.inspection is not None
        first.selection.choose(first.inspection.dataset.revision, (1,))
        first.profiles.height = 310
        first.views = replace(first.views, tab="Relationships", image_height=345)
        editor.activate(first.identity)
        editor.choose_route("Compare files")
        editor.navigation.context_tab = "History"
        editor.workspace.request_save(workspace, capture_session(editor))
        until(editor, lambda: not editor.workspace.busy)
        saved = read_session_workspace(workspace)
        assert saved.version == 3 and saved.layout_version == 2
        assert saved.files[0].recipe is not None
        assert saved.files[0].recipe.views.profile_height == 310
    finally:
        editor.close()
    second_path.unlink()
    replacement = tmp_path / "relinked.csv"
    replacement.write_bytes(b"x,y\n7,9\n8,6\n")
    restored = EditorController()
    try:
        restored.open_workspace(workspace)
        until(restored, lambda: not restored.workspace.busy)
        assert len(restored.files) == 2
        assert (
            restored.navigation.comparing
            and restored.navigation.context_tab == "History"
        )
        first, missing = restored.files
        assert first.inspection is not None and missing.recovery is not None
        assert first.inspection.dataset.row_ids.to_list() == [1, 2, 0]
        assert first.selection.row_ids == {1}
        assert first.profiles.height == 310
        assert first.views.image_height == 345
        assert first.views.tab == "Relationships"
        assert first.analysis.jobs.latest is None and not first.analysis.jobs.busy
        assert first.audio.player.snapshot.request is None
        restored.recover(missing.identity, replacement, False)
        until(restored, lambda: not restored.workspace.busy)
        assert missing.recovery is None and missing.inspection is not None
        assert first.inspection.dataset.row_ids.to_list() == [1, 2, 0]
        assert first_path.read_bytes() == b"x,y\n3,1\n1,2\n2,3\n"
    finally:
        restored.close()


def test_failed_source_draft_survives_session_capture(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    editor = EditorController()
    try:
        editor.active.open(missing)
        until(
            editor, lambda: editor.active.loader.status.phase.value == "Import failed"
        )
        captured = capture_session(editor)
        captured.workspace.validate()
        draft = captured.workspace.files[0].draft
        assert draft is not None and draft.path == str(missing)
    finally:
        editor.close()
