from pathlib import Path
from time import monotonic, sleep

import pytest

from datelier.application.sessions import EditorController, FileController
from datelier.gui.shell.layout import FileTab
from datelier.io.loading import LoadPhase


def wait_for_files(*files: FileController) -> None:
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
    editor = EditorController()
    try:
        blank = editor.active
        first = editor.new_file(source)
        second = editor.new_file(source)
        wait_for_files(first, second)
        first.plots.bins, second.plots.bins = 7, 13
        editor.activate(first.identity)
        editor.reorder((second.identity, blank.identity, first.identity))
        assert editor.active is first
        assert editor.files == [second, blank, first]
        editor.close_file(blank.identity)
        assert blank.closed and editor.active is first
        editor.close_file(first.identity)
        assert first.closed and editor.active is second and second.plots.bins == 13
        editor.close_file(second.identity)
        assert second.closed and len(editor.files) == 1
        assert editor.active.loader.active is None
        assert editor.active.identity not in (
            blank.identity,
            first.identity,
            second.identity,
        )
        assert editor.active.title == "Welcome"
        with pytest.raises(ValueError, match="unavailable"):
            editor.activate(first.identity)
        with pytest.raises(ValueError, match="exactly once"):
            editor.reorder((editor.active.identity, editor.active.identity))
    finally:
        editor.close()
    with pytest.raises(RuntimeError, match="closed"):
        editor.new_file()


def test_duplicate_filenames_have_distinct_native_ids(tmp_path: Path) -> None:
    editor = EditorController()
    try:
        first = editor.new_file()
        second = editor.new_file()
        first.imports.path = str(tmp_path / "first" / "data.csv")
        second.imports.path = str(tmp_path / "second" / "data.csv")
        from datelier.io.loading import LoadStatus

        first.loader.status = LoadStatus(path=Path(first.imports.path))
        second.loader.status = LoadStatus(path=Path(second.imports.path))
        assert (
            FileTab(first.identity, first.title, False).label.split("###")[0]
            == "data.csv"
        )
        assert (
            FileTab(second.identity, second.title, False).label.split("###")[0]
            == "data.csv"
        )
        assert (
            FileTab(first.identity, first.title, False).label
            != FileTab(second.identity, second.title, False).label
        )
        caption, _, identity = FileTab(
            first.identity, "data##literal.csv", False
        ).label.rpartition("###")
        assert caption.replace("\u200b", "") == "data##literal.csv"
        assert "##" not in caption
        assert identity == first.identity
    finally:
        editor.close()
