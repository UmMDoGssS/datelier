"""Headless publication, restoration and independent worker lifetime."""

from collections.abc import Callable
from pathlib import Path
from threading import Event
from time import monotonic, sleep

from datelier.application.sessions.dataset import DatasetRuntime
from datelier.core import SharedWorkers
from datelier.inspection.exploration import Explorer
from datelier.inspection.preview import PreviewCache
from datelier.io.jobs import DatasetExporter, DatasetLoader
from datelier.io.tabular import CsvImport, load_csv
from datelier.io.types import CsvOptions, ImportOptions
from datelier.pipeline import Sort
from datelier.pipeline.editing import DatasetEditor, HistoryAction
from datelier.plotting.scatter import LinkedSelection
from datelier.workspace.single import Workspace
from datelier.workspace.single.jobs import WorkspaceJobs
from datelier.workspace.single.restore import restore_workspace
from datelier.workspace.single.storage import reference_source, save_workspace


def runtime(
    workers: SharedWorkers, loader: DatasetLoader | None = None
) -> DatasetRuntime:
    return DatasetRuntime(
        loader or DatasetLoader(executor=workers),
        PreviewCache(executor=workers),
        DatasetEditor(executor=workers),
        DatasetExporter(executor=workers),
        Explorer(executor=workers),
        LinkedSelection(),
        WorkspaceJobs(executor=workers),
    )


def until(file: DatasetRuntime, ready: Callable[[], bool]) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        file.poll()
        file.poll_prepared()
        if ready():
            return
        sleep(0.001)
    raise AssertionError("Dataset did not settle")


def test_atomic_edit_restoration_and_close_keep_sibling_usable(tmp_path: Path) -> None:
    source = tmp_path / "data.csv"
    source.write_text("x,label\n3,c\n1,a\n2,b\n")
    original = source.read_bytes()
    with SharedWorkers() as workers:
        first, second = runtime(workers), runtime(workers)
        try:
            first.loader.request(source)
            second.loader.request(source)
            until(first, lambda: first.loader.active is not None)
            until(second, lambda: second.loader.active is not None)
            active = first.loader.active
            sibling = second.loader.active
            assert active is not None and sibling is not None
            assert (
                active.dataset.revision.dataset_id
                != sibling.dataset.revision.dataset_id
            )
            first.selection.choose(active.dataset.revision, (0,))
            first.editor.request(Sort(("x",)))
            until(first, lambda: not first.editor.busy)
            edited = first.loader.active
            assert edited is not None
            assert edited.dataset.row_ids.to_list() == [1, 2, 0]
            assert not first.selection.row_ids
            assert first.editor.pipeline is not None
            assert second.loader.active is sibling
            assert sibling.dataset.row_ids.to_list() == [0, 1, 2]
            saved = tmp_path / "saved.datelier"
            pipeline = first.editor.pipeline
            recipe = Workspace(
                reference_source(pipeline.source.source),
                active.imported.format,
                active.imported.options,
                pipeline.history,
                pipeline.cursor,
            )
            save_workspace(saved, recipe)
            first.install(restore_workspace(saved))
            assert first.loader.active is not None
            assert first.loader.active.dataset.row_ids.to_list() == [1, 2, 0]
            first.editor.request(HistoryAction.UNDO)
            until(first, lambda: not first.editor.busy)
            assert first.loader.active.dataset.row_ids.to_list() == [0, 1, 2]
            first.close()
            first.close()
            assert (
                first.loader.active
                is first.editor.pipeline
                is first.editor.inspection
                is None
            )
            assert not first.poll().loaded
            second.editor.request(Sort(("x",), True))
            until(second, lambda: not second.editor.busy)
            assert second.loader.active is not None
            assert second.loader.active.dataset.row_ids.to_list() == [0, 2, 1]
            assert source.read_bytes() == original
        finally:
            first.close()
            second.close()


def test_closed_runtime_cannot_publish_executing_import(tmp_path: Path) -> None:
    source = tmp_path / "data.csv"
    source.write_text("x\n1\n2\n")
    started, release = Event(), Event()

    def importer(path: Path, options: ImportOptions | None) -> CsvImport:
        started.set()
        assert release.wait(5)
        assert options is None or isinstance(options, CsvOptions)
        return load_csv(path, options)

    with SharedWorkers() as workers:
        loader = DatasetLoader(importer, executor=workers)
        file = runtime(workers, loader)
        try:
            file.loader.request(source)
            assert started.wait(5)
            file.close()
            release.set()
            assert not file.poll().loaded
            assert file.loader.active is None
            assert workers.submit(lambda: 7).result(5) == 7
        finally:
            release.set()
            file.close()
