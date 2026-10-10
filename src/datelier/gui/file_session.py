"""Presentation coordination for a file runtime and its migrating native views."""

from concurrent.futures import Executor
from dataclasses import dataclass, field, replace
from pathlib import Path
from uuid import uuid4

from datelier.analysis.jobs import AnalysisJobs
from datelier.analysis.plots import AnalysisPlots
from datelier.application.dataset import DatasetRuntime
from datelier.application.schema import SchemaController
from datelier.core.column_roles import REFERENCE_ROLES
from datelier.gui.analysis.session import AnalysisSession
from datelier.gui.arrays.mapping_controls import MappingControls
from datelier.gui.arrays.records import ArrayRecords
from datelier.gui.arrays.view import ArrayView
from datelier.gui.audio.view import AudioView
from datelier.gui.checkpoints.view import CheckpointView
from datelier.gui.data.export import ExportControls
from datelier.gui.data.import_controls import ImportControls
from datelier.gui.data.operations import OperationControls
from datelier.gui.data.schema import SchemaPanel
from datelier.gui.data.table import TableView
from datelier.gui.exploration import ExplorationView
from datelier.gui.images.view import ImageView
from datelier.gui.inspect.view import InspectView
from datelier.gui.objects.sessions import RecordViews
from datelier.gui.plots.controls import PlotControls
from datelier.gui.references.view import ReferenceView
from datelier.gui.text.view import TextView
from datelier.gui.workspace.controls import WorkspaceControls
from datelier.gui.workspace.preferences import PreferenceControls
from datelier.gui.workspace.state import (
    restore_plots,
    restore_view_settings,
    restore_views,
)
from datelier.inspection.arrays.jobs import ArrayJobs
from datelier.inspection.arrays.slices import SliceSettings
from datelier.inspection.audio.playback.controller import AudioPlayback
from datelier.inspection.checkpoints.jobs import CheckpointJobs
from datelier.inspection.exploration import Explorer
from datelier.inspection.preview import PreviewCache
from datelier.inspection.references.jobs import ReferenceJobs
from datelier.io.arrays.storage import ArrayStore
from datelier.io.exporting import DatasetExporter
from datelier.io.loading import DatasetLoader
from datelier.io.types import ArrayOptions, ImportFormat, MediaOptions
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
    inspect: InspectView = field(default_factory=InspectView)
    references: ReferenceJobs = field(default_factory=ReferenceJobs)
    reference_view: ReferenceView = field(default_factory=ReferenceView)
    identity: str = field(default_factory=lambda: uuid4().hex)
    closed: bool = False
    recovery: RestoredSessionFile | None = None
    deferred: RestoredSessionFile | None = None
    focus_inspect: bool = False
    focus_source: bool = False
    panel_scroll: dict[str, tuple[float, float]] = field(default_factory=dict)
    record_views: RecordViews = field(default_factory=RecordViews)
    view_name: str = ""
    arrays: ArrayJobs = field(default_factory=ArrayJobs)
    array_view: ArrayView = field(default_factory=ArrayView)
    array_mapping: MappingControls = field(default_factory=MappingControls)
    array_records: ArrayRecords = field(default_factory=ArrayRecords)
    checkpoints: CheckpointJobs = field(default_factory=CheckpointJobs)
    checkpoint_view: CheckpointView = field(default_factory=CheckpointView)
    text: TextView = field(default_factory=TextView)
    images: ImageView = field(default_factory=ImageView)
    audio: AudioView = field(default_factory=AudioView)
    schema_controller: SchemaController = field(init=False)
    schema_panel: SchemaPanel = field(init=False)
    runtime: DatasetRuntime = field(init=False)

    def __post_init__(self) -> None:
        self.runtime = DatasetRuntime(
            self.loader,
            self.pages,
            self.editor,
            self.exporter,
            self.explorer,
            self.selection,
            self.workspace.jobs,
        )
        self.schema_controller = SchemaController(self.editor.request)
        self.schema_panel = SchemaPanel(self.schema_controller)

    @classmethod
    def create(
        cls,
        preferences: PreferenceControls,
        *,
        executor: Executor | None = None,
        source_path: Path | None = None,
        workspace_path: Path | None = None,
        loader_override: DatasetLoader | None = None,
        array_store: ArrayStore | None = None,
        playback: AudioPlayback | None = None,
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
            inspect=InspectView(executor),
            record_views=RecordViews(executor),
            arrays=ArrayJobs(executor, store=array_store),
            array_mapping=MappingControls(executor),
            array_records=ArrayRecords(executor),
            checkpoints=CheckpointJobs(executor),
            text=TextView(executor),
            images=ImageView(executor),
            audio=AudioView(executor, playback),
        )
        return session

    def install_restored(self, restored: RestoredWorkspace) -> bool:
        self.record_views.clear()
        self.array_view.plotted.clear()
        self.array_view.raw_columns.clear()
        if self.checkpoints.catalog is not None:
            self.checkpoints.unbind()
        self.checkpoint_view.observed_path = None
        if restored.inspection.imported.checkpoint_catalog is not None:
            self.checkpoints.bind(
                restored.inspection.imported.checkpoint_catalog,
                restored.inspection.dataset.revision,
            )
        self.focus_inspect = False
        self.runtime.install(restored)
        self.controls.path = str(restored.pipeline.source.source.path)
        self.controls.bind_settings(
            restored.workspace.format, restored.workspace.options
        )
        self.table.reset()
        adjusted = restore_views(self, restored.workspace)
        if adjusted:
            self.workspace.jobs.message += (
                " Saved plot settings were adjusted to the current columns and charts."
            )
        self.explorer.request(restored.inspection.dataset, self.plots.settings())
        return adjusted

    def poll(self) -> None:
        if self.closed:
            return
        changes = self.runtime.poll()
        if changes.loaded:
            self.record_views.clear()
            self.array_view.plotted.clear()
            self.array_view.raw_columns.clear()
            self.arrays.settings = SliceSettings()
            self.checkpoints.settings = SliceSettings()
            self.checkpoint_view.observed_path = None
            assert self.loader.active is not None
            self.recovery = None
            self.deferred = None
            imported = self.loader.active.imported
            self.controls.path = str(imported.dataset.source.path)
            self.controls.bind_settings(imported.format, imported.options)
            self.table.reset()
            self.analysis.controls.bind(self.loader.active.dataset)
            restore_plots(
                self.plots, self.loader.active.dataset, self.preferences.value.plots
            )
            defaults = self.preferences.value.views
            restore_view_settings(
                self,
                replace(
                    defaults,
                    references=replace(defaults.references, roots=(), mappings=()),
                    array_slice=None,
                    checkpoint_slice=None,
                ),
            )
            self.focus_inspect = imported.format == ImportFormat.MEDIA
            self.focus_source = (
                imported.format
                in (ImportFormat.OBJECT, ImportFormat.ARRAY, ImportFormat.CHECKPOINT)
                and not self.view_name
            )
            self.explorer.request(self.loader.active.dataset, self.plots.settings())
        if changes.restored is not None:
            self.install_restored(changes.restored)
        edited = changes.edited
        if edited is not None:
            self.table.reset()
            self.analysis.controls.bind(edited.dataset)
            self.plots.bind(edited.dataset)
            self.explorer.request(edited.dataset, self.plots.settings())
        self.analysis.sync_dimensions(self.plots)
        self.analysis.poll(self.loader.active.dataset if self.loader.active else None)
        if self.analysis.sync_colors(self.plots) and self.loader.active is not None:
            self.explorer.request(self.loader.active.dataset, self.plots.settings())
        self.runtime.poll_prepared()
        self.reference_view.textures.begin_frame()
        active = self.loader.active
        options = active.imported.options if active else None
        array_columns = (
            frozenset(
                name
                for name in active.dataset.table.columns
                if options.mapping_for(active.imported.array_catalog, name) is not None
            )
            if active and isinstance(options, ArrayOptions) and options.mapping is None
            else frozenset()
        )
        self.reference_view.array_columns = array_columns
        if active and any(
            info.role in REFERENCE_ROLES and info.name not in array_columns
            for info in active.dataset.roles or ()
        ):
            if self.references.source != active.dataset.source.path or (
                self.references.revision is not None
                and self.references.revision.dataset_id
                != active.dataset.revision.dataset_id
            ):
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
        self.inspect.sync(
            active.dataset if active else None,
            self.selection,
            "text"
            if active
            and isinstance(active.imported.options, MediaOptions)
            and active.imported.options.text_lines
            else None,
        )
        self.record_views.poll(self)
        if active is not None and active.imported.array_catalog is not None:
            self.arrays.bind(active.imported.array_catalog, active.dataset.revision)
        elif self.arrays.catalog is not None and self.deferred is None:
            self.arrays.unbind()
        self.arrays.poll()
        self.array_mapping.bind(self.arrays.catalog)
        self.array_mapping.poll()
        self.array_records.sync(self)
        if active is not None and active.imported.checkpoint_catalog is not None:
            self.checkpoints.bind(
                active.imported.checkpoint_catalog, active.dataset.revision
            )
        elif self.checkpoints.catalog is not None:
            self.checkpoints.unbind()
        self.checkpoints.poll()
        self.text.sync(self)
        self.images.sync(self)
        self.audio.sync(self)
        self.schema_controller.refresh(self.loader.active, busy=self.editor.busy)

    def install_session_file(self, result: RestoredSessionFile) -> None:
        from datelier.gui.workspace.session_install import install_session_file

        install_session_file(self, result)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.record_views.clear()
        self.audio.close(self.identity)
        self.arrays.close()
        self.array_mapping.close()
        self.array_records.close()
        self.checkpoints.close()
        self.text.close()
        self.images.close()
        self.array_view.raw_columns.clear()
        self.array_view.plotted.clear()
        self.reference_view.textures.clear()
        self.references.close()
        self.inspect.close()
        self.runtime.close()
        self.analysis.close(wait=False)
        self.schema_controller.refresh(None, busy=False)
        self.panel_scroll.clear()
        self.recovery = None
        self.deferred = None
