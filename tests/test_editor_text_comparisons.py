"""Saved text mappings, explicit preparation, correct tab selection and recovery."""

from pathlib import Path
from time import monotonic, sleep

from datelier.gui.editor_session import EditorSession
from datelier.inspection.text.comparisons.settings import (
    TextComparisonSettings,
    TextComparisonSource,
)
from datelier.inspection.text.types import CorpusMode, TextScope, TextSource
from datelier.io.loading import LoadPhase
from datelier.workspace.session_storage import read_session_workspace


def wait(editor: EditorSession) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if (
            not editor.opening.busy
            and not editor.workspace_jobs.busy
            and not editor.text_comparison_jobs.busy
            and all(
                file.loader.status.phase != LoadPhase.LOADING for file in editor.files
            )
        ):
            return
        sleep(0.001)
    raise AssertionError("Text comparison editor jobs did not finish")


def test_saved_explicit_comparison_link_and_partial_recovery(tmp_path: Path) -> None:
    paths = (tmp_path / "first.csv", tmp_path / "second.csv")
    paths[0].write_text("text\na\nb b\n")
    paths[1].write_text("text\nc c c\nd d d d\n")
    workspace = tmp_path / "session.datelier"
    editor = EditorSession()
    try:
        editor.opening.request(paths, editor.active_id)
        wait(editor)
        first, second = editor.files
        recipe = TextComparisonSettings(
            tuple(
                TextComparisonSource(
                    file.identity,
                    "text",
                    TextSource.INLINE,
                    scope=TextScope(CorpusMode.COLLECTION),
                )
                for file in editor.files
            ),
            bins=4,
        )
        editor.text_comparisons = (recipe,)
        editor.poll()
        assert editor.text_comparison_jobs.started == 0
        editor.text_comparison_jobs.request()
        wait(editor)
        result = editor.text_comparison_jobs.active
        assert result
        editor.select_text_comparison(result, 1, 3)
        deadline = monotonic() + 5
        while not second.selection.row_ids and monotonic() < deadline:
            editor.poll()
            sleep(0.001)
        assert second.selection.row_ids == {0, 1} and not first.selection.row_ids
        assert editor.active is second and second.table.target_row == 1
        editor.save_workspace(workspace)
        wait(editor)
        saved = read_session_workspace(workspace)
        assert saved.text_comparisons == (recipe,)
        assert "frequencies" not in workspace.read_text()
        paths[0].rename(tmp_path / "moved.csv")
        editor.open_workspace(workspace)
        wait(editor)
        failed, good = editor.files
        assert failed.recovery and good.loader.active
        assert (
            not editor.text_comparison_jobs.busy
            and editor.text_comparison_jobs.active is None
        )
        assert editor.text_comparison_jobs.started == 1
        assert editor.text_comparisons == (recipe,)
        editor.recover_source(failed.identity, relink=tmp_path / "moved.csv")
        wait(editor)
        assert failed.loader.active and editor.text_comparison_jobs.active is None
        editor.close_tab(failed.identity)
        editor.poll()
        assert editor.text_comparisons[0].sources == (recipe.sources[1],)
        assert editor.text_comparison_jobs.active is None
        editor.save_workspace(tmp_path / "closed.datelier")
        wait(editor)
        assert (
            editor.workspace_jobs.saved
            and editor.workspace_jobs.saved.path.name == "closed.datelier"
        )
    finally:
        editor.close()
