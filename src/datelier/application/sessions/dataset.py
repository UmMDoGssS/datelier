"""Dataset publication and worker ownership without presentation dependencies."""

from dataclasses import dataclass

from datelier.inspection.exploration import Explorer
from datelier.inspection.preview import PreviewCache
from datelier.inspection.table import Inspection
from datelier.io.exporting import DatasetExporter
from datelier.io.loading import DatasetLoader, LoadPhase, LoadStatus
from datelier.pipeline.editing import DatasetEditor
from datelier.plotting.scatter import LinkedSelection
from datelier.workspace.single.jobs import WorkspaceJobs
from datelier.workspace.single.restore import RestoredWorkspace


@dataclass(frozen=True)
class DatasetChanges:
    loaded: bool = False
    edited: Inspection | None = None
    restored: RestoredWorkspace | None = None


@dataclass
class DatasetRuntime:
    loader: DatasetLoader
    pages: PreviewCache
    editor: DatasetEditor
    exporter: DatasetExporter
    explorer: Explorer
    selection: LinkedSelection
    workspace: WorkspaceJobs
    closed: bool = False

    def poll(self) -> DatasetChanges:
        if self.closed:
            return DatasetChanges()
        loaded = self.loader.poll()
        if loaded:
            assert self.loader.active is not None
            self.editor.bind(self.loader.active)
            self._publish(self.loader.active)
        if self.loader.status.phase == LoadPhase.LOADING:
            self.editor.abandon()
            self.workspace.abandon()
        restored = self.workspace.poll(self.loader.revision)
        if restored is not None:
            # The presentation coordinator applies saved view settings before
            # requesting any exploration with the restored recipe.
            return DatasetChanges(loaded=loaded, restored=restored)
        edited = self.editor.poll(self.loader.revision)
        if edited is not None:
            self._publish(edited)
        return DatasetChanges(loaded=loaded, edited=edited)

    def install(self, restored: RestoredWorkspace) -> None:
        if self.closed:
            raise ValueError("The dataset runtime is closed")
        self.loader.abandon()
        self.loader.status = LoadStatus(
            LoadPhase.READY, restored.pipeline.source.source.path
        )
        self.editor.bind(restored.inspection)
        self.editor.pipeline = restored.pipeline
        self._publish(restored.inspection)

    def _publish(self, inspection: Inspection) -> None:
        self.loader.active = inspection
        self.pages.bind(inspection)
        self.selection.bind(inspection.dataset.revision)

    def poll_prepared(self) -> None:
        """Publish derived jobs after coordinators have applied source changes."""
        if self.closed:
            return
        self.explorer.poll(self.loader.revision)
        self.exporter.poll()
        self.pages.poll()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.loader.close()
        self.pages.close()
        self.editor.close()
        self.exporter.close()
        self.explorer.close()
        self.workspace.close()
        self.loader.active = None
        self.editor.pipeline = None
        self.editor.inspection = None
