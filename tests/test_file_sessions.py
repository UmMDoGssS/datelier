from pathlib import Path
from threading import Event
from time import monotonic, sleep

from datelier.analysis.types import EmbeddingResult, PreparedInput
from datelier.application.file import FileController
from datelier.core.jobs import SharedWorkers
from datelier.io.csv import load_csv
from datelier.io.loading import DatasetLoader, LoadPhase
from datelier.io.types import ImportOptions, ImportResult
from datelier.pipeline.editing import HistoryAction
from datelier.pipeline.operations import Sort


def wait_for_files(*files: FileController) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        for file in files:
            file.poll()
        if all(
            file.loader.status.phase != LoadPhase.LOADING and not file.editor.busy
            for file in files
        ):
            return
        sleep(0.001)
    raise AssertionError("Files did not finish preparing")


def test_files_keep_independent_history_controls_and_colliding_row_ids(
    tmp_path: Path,
) -> None:
    train, test = tmp_path / "train.csv", tmp_path / "test.csv"
    train.write_text("x,y\n3,6\n1,2\n2,4\n")
    test.write_text("x,y\n30,60\n10,20\n20,40\n")
    originals = (train.read_bytes(), test.read_bytes())
    workers = SharedWorkers()
    first = FileController(workers)
    second = FileController(workers)
    try:
        first.loader.request(train)
        second.loader.request(test)
        wait_for_files(first, second)
        assert first.identity != second.identity
        assert first.loader.active is not None and second.loader.active is not None
        assert first.loader.active.dataset.row_ids.to_list() == [0, 1, 2]
        assert second.loader.active.dataset.row_ids.to_list() == [0, 1, 2]
        assert first.loader.revision != second.loader.revision
        first.editor.request(Sort(("x",)))
        wait_for_files(second, first)
        first.selection.choose(first.loader.active.dataset.revision, [1])
        second.selection.choose(second.loader.active.dataset.revision, [2])
        first.plots.bins, second.plots.bins = 7, 13
        first.analysis.controls.seed, second.analysis.controls.seed = 9, 19
        first.table.target_row, second.table.target_row = 2, 3
        for _ in range(30):
            second.poll()
            first.poll()
        assert first.editor.pipeline is not None
        assert first.editor.pipeline.can_undo
        assert second.editor.pipeline is not None
        assert not second.editor.pipeline.can_undo
        assert first.loader.active.dataset.row_ids.to_list() == [1, 2, 0]
        assert second.loader.active.dataset.table["x"].to_list() == [30, 10, 20]
        assert first.selection.row_ids == {1} and second.selection.row_ids == {2}
        assert (first.plots.bins, second.plots.bins) == (7, 13)
        assert (first.analysis.controls.seed, second.analysis.controls.seed) == (9, 19)
        assert (first.table.target_row, second.table.target_row) == (2, 3)
        assert not first.analysis.jobs.busy and not second.analysis.jobs.busy
        first.editor.request(HistoryAction.UNDO)
        wait_for_files(first, second)
        assert first.loader.active.dataset.table["x"].to_list() == [3, 1, 2]
        assert second.selection.row_ids == {2}
        assert (train.read_bytes(), test.read_bytes()) == originals
    finally:
        first.close()
        second.close()
        workers.shutdown()


def slow_embedding(prepared: PreparedInput) -> EmbeddingResult:
    """Spawned fixture: cancellation must stop an executing worker."""
    from datelier.analysis.types import Provenance

    sleep(10)
    return EmbeddingResult(
        prepared.revision,
        prepared.row_ids,
        prepared.positions,
        prepared.values[:, :2],
        Provenance(prepared.request, prepared.summary, (), 0),
    )


def test_closing_analyzing_tab_is_nonblocking_and_reaps_its_worker(
    tmp_path: Path,
) -> None:
    import multiprocessing as mp
    from concurrent.futures import CancelledError

    import pytest

    from datelier.analysis.jobs import AnalysisJobs
    from datelier.analysis.types import AnalysisRequest
    from datelier.application.editor import EditorController

    source = tmp_path / "source.csv"
    source.write_text("x,y\n1,2\n3,4\n5,6\n7,8\n")
    editor = EditorController()
    first = editor.new_file(source)
    second = editor.new_file(source)
    before = {process.pid for process in mp.active_children()}
    try:
        wait_for_files(first, second)
        assert first.loader.active is not None
        first.analysis.jobs.close()
        jobs = first.analysis.jobs = AnalysisJobs(
            slow_embedding, executor=editor.workers
        )
        jobs.request(first.loader.active.dataset, AnalysisRequest(("x", "y")))
        deadline = monotonic() + 5
        while "fitting" not in jobs.phase and monotonic() < deadline:
            sleep(0.001)
        assert "fitting" in jobs.phase
        future = jobs._future
        assert future is not None and not future.done()
        running = {
            process.pid for process in mp.active_children() if process.pid not in before
        }
        assert running
        started = monotonic()
        editor.close_file(first.identity)
        assert monotonic() - started < 0.5
        assert first.closed and editor.active is second
        assert first.loader.active is None and first.editor.pipeline is None
        with pytest.raises(CancelledError):
            future.result(5)
        editor.poll()
        assert second.loader.active is not None
        assert not first.analysis.jobs.results and not second.analysis.jobs.results
        assert not jobs.poll(second.loader.revision)
        assert running.isdisjoint(process.pid for process in mp.active_children())
    finally:
        editor.close()


def test_closed_loading_file_never_publishes_into_a_sibling(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_text("x,y\n1,2\n3,4\n")
    started, release = Event(), Event()
    workers = SharedWorkers()

    def importer(path: Path, options: ImportOptions | None) -> ImportResult:
        started.set()
        assert release.wait(3)
        return load_csv(path)

    loader = DatasetLoader(importer, executor=workers)
    first = FileController(workers, loader=loader)
    second = FileController(workers)
    try:
        first.loader.request(source)
        assert started.wait(3)
        first.close()
        second.loader.request(source)
        wait_for_files(second)
        active = second.loader.active
        assert active is not None
        release.set()
        deadline = monotonic() + 3
        while first.loader.retired_running and monotonic() < deadline:
            sleep(0.001)
        assert first.loader.retired_running == 0
        first.poll()
        second.poll()
        assert first.closed and first.loader.active is None
        assert second.loader.active is active
        assert first.loader.retired_running == 0
        assert not first.editor.busy and not first.analysis.jobs.busy
    finally:
        release.set()
        first.close()
        second.close()
        workers.shutdown()
