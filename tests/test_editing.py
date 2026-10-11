from pathlib import Path
from threading import Event
from time import monotonic, sleep

from datelier.inspection.table import Inspection, prepare_inspection
from datelier.io.tabular import load_csv
from datelier.pipeline import Comparison, Filter, Pipeline, Sort
from datelier.pipeline.editing import DatasetEditor, HistoryAction


def wait_edit(editor: DatasetEditor, active: Inspection) -> Inspection | None:
    deadline = monotonic() + 3
    result = None
    while editor.busy and monotonic() < deadline:
        result = editor.poll(active.dataset.revision)
        sleep(0.001)
    assert not editor.busy
    return result


def test_edit_preview_history_failure_and_revision(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("v\n3\n1\n2\n")
    active = prepare_inspection(load_csv(path))
    editor = DatasetEditor()
    try:
        editor.bind(active)
        editor.request(Sort(("v",)))
        result = wait_edit(editor, active)
        assert result is not None
        assert result.first_page.rows == (("1",), ("2",), ("3",))
        assert result.first_page.row_ids == (1, 2, 0)
        assert result.first_page.revision != active.first_page.revision
        editor.request(Filter("missing", Comparison.EQ, 1))
        assert wait_edit(editor, result) is None
        assert editor.inspection is result
        assert "failed" in editor.message
        editor.request(HistoryAction.UNDO)
        restored = wait_edit(editor, result)
        assert restored is not None and restored.dataset.table.equals(
            active.dataset.table
        )
        assert path.read_text() == "v\n3\n1\n2\n"
    finally:
        editor.close()


def test_stale_and_abandoned_edits_cannot_publish(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "data.csv"
    path.write_text("v\n2\n1\n")
    active = prepare_inspection(load_csv(path))
    started, release = Event(), Event()
    original = Pipeline.apply

    def slow(self: Pipeline, operation: Sort) -> Pipeline:
        started.set()
        assert release.wait(3)
        return original(self, operation)

    monkeypatch.setattr(Pipeline, "apply", slow)
    editor = DatasetEditor()
    try:
        editor.bind(active)
        editor.request(Sort(("v",)))
        assert started.wait(3)
        assert editor.poll(active.dataset.revision) is None
        newer = prepare_inspection(load_csv(path))
        release.set()
        assert wait_edit(editor, newer) is None
        assert "obsolete" in editor.message
        editor.bind(active)
        release.clear()
        started.clear()
        editor.request(Sort(("v",)))
        assert started.wait(3)
        editor.bind(newer)
        release.set()
        assert editor.poll(newer.dataset.revision) is None
        assert editor.inspection is newer
        assert editor.pipeline is not None and not editor.pipeline.history
    finally:
        release.set()
        editor.close()


def test_preview_preparation_failure_does_not_publish_candidate(
    tmp_path: Path, monkeypatch
) -> None:
    import datelier.pipeline.editing as editing

    path = tmp_path / "data.csv"
    path.write_text("v\n2\n1\n")
    active = prepare_inspection(load_csv(path))
    editor = DatasetEditor()
    editor.bind(active)
    original = editor.pipeline

    def failed(ignored: object) -> None:
        raise RuntimeError("summary preparation failed")

    monkeypatch.setattr(editing, "prepare_inspection", failed)
    try:
        editor.request(Sort(("v",)))
        assert wait_edit(editor, active) is None
        assert editor.pipeline is original and editor.inspection is active
        assert "summary preparation failed" in editor.message
    finally:
        editor.close()
