"""File-owned inspection state and publication, independent of GUI rendering."""

from concurrent.futures import Executor
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from datelier.analysis.jobs import AnalysisJobs
from datelier.analysis.plots import AnalysisPlots
from datelier.core.column_roles import REFERENCE_ROLES
from datelier.gui.analysis.session import AnalysisSession
from datelier.gui.data.export import ExportControls
from datelier.gui.data.import_controls import ImportControls
from datelier.gui.data.operations import OperationControls
from datelier.gui.data.table import TableView
from datelier.gui.exploration import ExplorationView
from datelier.gui.plots.controls import PlotControls
from datelier.gui.references.view import ReferenceView
from datelier.gui.workspace.controls import WorkspaceControls
from datelier.gui.workspace.preferences import PreferenceControls
from datelier.gui.workspace.state import (
    restore_plots,
    restore_view_settings,
    restore_views,
)
from datelier.inspection.exploration import Explorer
from datelier.inspection.preview import PreviewCache
from datelier.inspection.references.jobs import ReferenceJobs
from datelier.io.exporting import DatasetExporter
from datelier.io.loading import DatasetLoader, LoadPhase, LoadStatus
from datelier.io.types import ImportFormat
from datelier.pipeline.editing import DatasetEditor
from datelier.plotting.selection import LinkedSelection
from datelier.workspace.jobs import WorkspaceJobs
from datelier.workspace.restore import RestoredWorkspace
from datelier.workspace.session_restore import RestoredSessionFile


@dataclass
class FileSession:
    loader: DatasetLoader
    pages: PreviewCache
    table: TableView
    controls: ImportControls
    editor: DatasetEditor
    operations: OperationControls
    exporter: DatasetExporter
    exports: ExportControls
    explorer: Explorer
    exploration: ExplorationView
    plots: PlotControls
    selection: LinkedSelection
    analysis: AnalysisSession
    workspace: WorkspaceControls
    preferences: PreferenceControls  # Borrowed application defaults, never owned.
    references: ReferenceJobs = field(default_factory=ReferenceJobs)
    reference_view: ReferenceView = field(default_factory=ReferenceView)
    identity: str = field(default_factory=lambda: uuid4().hex)
    closed: bool = False
    recovery: RestoredSessionFile | None = None
    panel_scroll: dict[str, tuple[float, float]] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        preferences: PreferenceControls,
        *,
        executor: Executor | None = None,
        source_path: Path | None = None,
        workspace_path: Path | None = None,
        loader_override: DatasetLoader | None = None,
    ) -> FileSession:
        loader = (
            loader_override
            if loader_override is not None
            else DatasetLoader(executor=executor)
        )
        pages = PreviewCache(executor=executor)
        view = TableView()
        controls = ImportControls(path=str(source_path) if source_path else "")
        editor = DatasetEditor(executor=executor)
        operations = OperationControls()
        exporter = DatasetExporter(executor=executor)
        exports = ExportControls()
        explorer = Explorer(executor=executor)
        exploration = ExplorationView()
        plot_controls = PlotControls()
        selection = LinkedSelection()
        analysis = AnalysisSession(
            jobs=AnalysisJobs(executor=executor), plots=AnalysisPlots(executor=executor)
        )
        workspace = WorkspaceControls(
            path=str(workspace_path) if workspace_path else "",
            jobs=WorkspaceJobs(executor=executor),
        )
        session = cls(
            loader,
            pages,
            view,
            controls,
            editor,
            operations,
            exporter,
            exports,
            explorer,
            exploration,
            plot_controls,
            selection,
            analysis,
            workspace,
            preferences,
            references=ReferenceJobs(executor),
        )
        return session

    def install_restored(self, restored: RestoredWorkspace) -> bool:
        self.loader.abandon()
        self.loader.active = restored.inspection
        self.loader.status = LoadStatus(
            LoadPhase.READY, restored.pipeline.source.source.path
        )
        self.controls.path = str(restored.pipeline.source.source.path)
        self.controls.bind_settings(
            restored.workspace.format, restored.workspace.options
        )
        self.editor.bind(restored.inspection)
        self.editor.pipeline = restored.pipeline
        self.pages.bind(restored.inspection)
        self.table.reset()
        adjusted = restore_views(self, restored.workspace)
        if adjusted:
            self.workspace.jobs.message += (
                " Saved plot settings were adjusted to the current columns and charts."
            )
        self.selection.bind(restored.inspection.dataset.revision)
        self.explorer.request(restored.inspection.dataset, self.plots.settings())
        return adjusted

    def poll(self) -> None:
        if self.closed:
            return
        if self.loader.poll():
            assert self.loader.active is not None
            self.recovery = None
            imported = self.loader.active.imported
            self.controls.path = str(imported.dataset.source.path)
            self.controls.bind_settings(imported.format, imported.options)
            self.editor.bind(self.loader.active)
            self.pages.bind(self.loader.active)
            self.table.reset()
            self.analysis.controls.bind(self.loader.active.dataset)
            restore_plots(
                self.plots, self.loader.active.dataset, self.preferences.value.plots
            )
            restore_view_settings(self, self.preferences.value.views)
            self.selection.bind(self.loader.active.dataset.revision)
            self.explorer.request(self.loader.active.dataset, self.plots.settings())
        if self.loader.status.phase == LoadPhase.LOADING:
            self.editor.abandon()
            self.workspace.jobs.abandon()
        restored = self.workspace.jobs.poll(self.loader.revision)
        if restored is not None:
            self.install_restored(restored)
        edited = self.editor.poll(self.loader.revision)
        if edited is not None:
            self.loader.active = edited
            self.pages.bind(edited)
            self.table.reset()
            self.analysis.controls.bind(edited.dataset)
            self.plots.bind(edited.dataset)
            self.selection.bind(edited.dataset.revision)
            self.explorer.request(edited.dataset, self.plots.settings())
        self.analysis.sync_dimensions(self.plots)
        completed = self.analysis.poll(
            self.loader.active.dataset if self.loader.active else None
        )
        if completed:
            self.exploration.tab = "Relationships"
            self.plots.relationship_chart = "Scatter"
        if self.analysis.sync_colors(self.plots) and self.loader.active is not None:
            self.explorer.request(self.loader.active.dataset, self.plots.settings())
        self.explorer.poll(self.loader.revision)
        self.exporter.poll()
        self.pages.poll()
        self.reference_view.textures.begin_frame()
        active = self.loader.active
        if active and any(
            info.role in REFERENCE_ROLES for info in active.dataset.roles or ()
        ):
            if self.references.source != active.dataset.source.path:
                self.reference_view.textures.clear()
            self.references.bind(
                active.dataset.source.path,
                active.dataset.revision,
                discover_nearby=active.imported.format != ImportFormat.MEDIA,
            )
        elif self.references.source is not None:
            self.references.unbind()
            self.reference_view.textures.clear()
        self.references.poll()

    def install_session_file(self, result: RestoredSessionFile) -> None:
        self.panel_scroll = {name: (x, y) for name, x, y in result.file.panel_scroll}
        if result.restored is not None:
            adjusted = self.install_restored(result.restored)
            self.selection.choose(
                result.restored.inspection.dataset.revision, result.file.selection
            )
            message = result.message
            if adjusted:
                message += (
                    " Saved view settings were adjusted to the available columns."
                )
            if message:
                self.loader.status = LoadStatus(
                    LoadPhase.READY, self.loader.status.path, message.strip()
                )
            self.recovery = None
        elif result.message:
            self.recovery = result
            recipe, draft = result.file.recipe, result.file.draft
            if recipe is not None:
                self.controls.path = recipe.source.path
                self.controls.bind_settings(recipe.format, recipe.options)
            elif draft is not None:
                self.controls.path = draft.path
                self.controls.bind_settings(draft.format, draft.options)
            self.loader.status = LoadStatus(
                LoadPhase.FAILED, Path(self.controls.path), result.message
            )

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.reference_view.textures.clear()
        self.references.close()
        self.loader.close()
        self.pages.close()
        self.editor.close()
        self.exporter.close()
        self.explorer.close()
        self.analysis.close(wait=False)
        self.workspace.jobs.close()
        self.loader.active = None
        self.editor.pipeline = None
        self.editor.inspection = None
        self.panel_scroll.clear()
        self.recovery = None
