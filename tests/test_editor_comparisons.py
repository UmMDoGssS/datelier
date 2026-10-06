from pathlib import Path
from time import monotonic, sleep

from datelier.gui.editor_session import EditorSession
from datelier.inspection.comparison_settings import (
    ComparisonSettings,
    ComparisonSource,
    Normalization,
)
from datelier.io.loading import LoadPhase
from datelier.pipeline.operations import Sort
from datelier.workspace.session_storage import read_session_workspace


def wait(editor: EditorSession) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if (
            not editor.comparison_jobs.busy
            and not editor.workspace_jobs.busy
            and all(
                file.loader.status.phase != LoadPhase.LOADING and not file.editor.busy
                for file in editor.files
            )
        ):
            return
        sleep(0.001)
    raise AssertionError("Editor comparison did not finish")


def test_editor_comparison_selection_workspace_and_closed_mapping(
    tmp_path: Path,
) -> None:
    train, test = tmp_path / "train.csv", tmp_path / "test.csv"
    train.write_text("x\n3.0\n0.0\n2.0\n1.0\n")
    test.write_text("different\n0.0\n3.0\n")
    editor = EditorSession()
    try:
        first = editor.active
        first.loader.request(train)
        second = editor.new_tab(test)
        wait(editor)
        first.editor.request(Sort(("x",)))
        wait(editor)
        sources = (
            ComparisonSource(first.identity, "x", "Train", (0.1, 0.4, 1.0, 1.0)),
            ComparisonSource(
                second.identity, "different", "Test", (1.0, 0.4, 0.1, 1.0)
            ),
        )
        editor.comparisons = (
            ComparisonSettings(sources, 2, normalization=Normalization.COUNT),
        )
        wait(editor)
        result = editor.comparison_jobs.states[0].result
        assert result is not None
        assert second.loader.revision is not None
        second.selection.choose(second.loader.revision, (0,))
        editor.select_comparison(result, 0, 0)
        wait(editor)
        assert editor.active is first and first.selection.row_ids == frozenset((1, 3))
        assert second.selection.row_ids == frozenset((0,)) and first.table.jump
        saved = tmp_path / "saved.datelier"
        editor.save_workspace(saved)
        wait(editor)
        settings = editor.comparisons
        assert read_session_workspace(saved).comparisons == settings
        editor.open_workspace(saved)
        wait(editor)
        assert editor.comparisons == settings
        restored = editor.comparison_jobs.states[0].result
        assert restored is not None and restored is not result
        assert restored.series[0].origin.file_id == first.identity
        assert all(
            not file.analysis.jobs.results and not file.analysis.jobs.busy
            for file in editor.files
        )
        editor.close_tab(second.identity)
        wait(editor)
        assert len(editor.comparisons[0].sources) == 1
        assert editor.comparison_jobs.states[0].result is None
        editor.save_workspace(saved, overwrite=True)
        wait(editor)
        assert len(read_session_workspace(saved).files) == 1
    finally:
        editor.close()
