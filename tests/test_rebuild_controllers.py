"""Behavioral gates for the fresh, GUI-free runtime."""

from pathlib import Path
from time import monotonic, sleep

from datelier.application.editor import EditorController
from datelier.application.file import FileController
from datelier.pipeline.operations import Sort


def ready(editor: EditorController, file: FileController) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if file.inspection and file.explorer.active and file.records.jobs.active:
            return
        sleep(0.002)
    raise AssertionError(file.loader.status)


def test_tabs_sorted_identity_and_explicit_operations(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    original = b"x,label\n3,three\n1,one\n2,two\n"
    source.write_bytes(original)
    editor = EditorController()
    try:
        first = editor.active
        first.open(source)
        ready(editor, first)
        second = editor.new_file(source)
        ready(editor, second)
        first.editor.request(Sort(("x",)))
        deadline = monotonic() + 5
        while first.editor.busy and monotonic() < deadline:
            editor.poll()
            sleep(0.002)
        assert first.inspection is not None and second.inspection is not None
        assert first.inspection.dataset.row_ids.to_list() == [1, 2, 0]
        assert second.inspection.dataset.row_ids.to_list() == [0, 1, 2]
        assert first.analysis.jobs.latest is None
        assert first.text.jobs.profile is None
        assert first.audio.player.snapshot.request is None
        assert source.read_bytes() == original
        editor.choose_route("Compare files")
        editor.activate(first.identity)
        assert not editor.navigation.comparing
        editor.close_file(first.identity)
        assert first.closed and first.inspection is None
        assert second.inspection is not None
    finally:
        editor.close()
        editor.close()
