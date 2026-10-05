from pathlib import Path
from time import monotonic, sleep

import pytest

from datelier.gui.editor_session import EditorSession
from datelier.gui.file_session import FileSession
from datelier.gui.tabs import tab_label
from datelier.io.loading import LoadPhase


def wait_for_files(*files: FileSession) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        for file in files:
            file.poll()
        if all(file.loader.status.phase != LoadPhase.LOADING for file in files):
            return
        sleep(0.001)
    raise AssertionError("Files did not finish loading")


def test_switch_reorder_close_and_last_tab_replacement(tmp_path: Path) -> None:
    source = tmp_path / "data.csv"
    source.write_text("x,y\n3,6\n1,2\n2,4\n")
    editor = EditorSession()
    try:
        blank = editor.active
        first = editor.new_tab(source)
        second = editor.new_tab(source)
        wait_for_files(first, second)
        first.plots.bins, second.plots.bins = 7, 13
        editor.activate(first.identity)
        editor.reorder((second.identity, blank.identity, first.identity))
        assert editor.active is first
        assert editor.files == [second, blank, first]
        editor.close_tab(blank.identity)
        assert blank.closed and editor.active is first
        editor.close_tab(first.identity)
        assert first.closed and editor.active is second and second.plots.bins == 13
        editor.close_tab(second.identity)
        assert second.closed and len(editor.files) == 1
        assert editor.active.loader.active is None
        assert editor.active.identity not in (
            blank.identity,
            first.identity,
            second.identity,
        )
        assert tab_label(editor.active).startswith("Welcome###")
        with pytest.raises(ValueError, match="closed"):
            editor.activate(first.identity)
        with pytest.raises(ValueError, match="exactly once"):
            editor.reorder((editor.active.identity, editor.active.identity))
    finally:
        editor.close()
    with pytest.raises(RuntimeError, match="closed"):
        editor.new_tab()


def test_duplicate_filenames_have_distinct_native_ids(tmp_path: Path) -> None:
    editor = EditorSession()
    try:
        first = editor.new_tab()
        second = editor.new_tab()
        first.controls.path = str(tmp_path / "first" / "data.csv")
        second.controls.path = str(tmp_path / "second" / "data.csv")
        from datelier.io.loading import LoadStatus

        first.loader.status = LoadStatus(path=Path(first.controls.path))
        second.loader.status = LoadStatus(path=Path(second.controls.path))
        assert tab_label(first).split("###")[0] == "data.csv"
        assert tab_label(second).split("###")[0] == "data.csv"
        assert tab_label(first) != tab_label(second)
    finally:
        editor.close()
