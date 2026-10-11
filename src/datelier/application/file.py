"""File-owned domain services; no native widgets or rendering imports."""

from concurrent.futures import Executor
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from datelier.analysis.jobs import AnalysisJobs
from datelier.analysis.plots import AnalysisPlots
from datelier.analysis.types import Algorithm, EmbeddingResult
from datelier.application.analysis import AnalysisController
from datelier.application.audio import AudioController
from datelier.application.columns import ColumnChoice
from datelier.application.dataset import DatasetRuntime
from datelier.application.images import ImageController
from datelier.application.import_settings import DEFAULTS, import_draft
from datelier.application.imports.controller import ImportController
from datelier.application.media_input import MediaInput
from datelier.application.plot_settings import PlotState
from datelier.application.profiles import ProfileController
from datelier.application.record_views import RecordViews
from datelier.application.records import RecordController
from datelier.application.references import ReferenceController
from datelier.application.schema import SchemaController
from datelier.application.settings_restore import restore_analysis, restore_plots
from datelier.application.sources.numeric import NumericSourceController
from datelier.application.sources.objects import ObjectController
from datelier.application.sources.records import ArrayRecordController
from datelier.application.table import TableController
from datelier.application.text import TextController
from datelier.core.column_roles import REFERENCE_ROLES, ColumnRole
from datelier.inspection.arrays.jobs import ArrayJobs
from datelier.inspection.arrays.slices import SliceSettings
from datelier.inspection.audio.playback.controller import AudioPlayback
from datelier.inspection.checkpoints.jobs import CheckpointJobs
from datelier.inspection.exploration import Explorer, PlotSettings
from datelier.inspection.preview import PreviewCache
from datelier.inspection.references.jobs import ReferenceJobs
from datelier.inspection.table import Inspection
from datelier.inspection.text.list_records import is_text_field
from datelier.io.arrays.storage import ArrayStore
from datelier.io.exporting import DatasetExporter
from datelier.io.loading import DatasetLoader, LoadPhase
from datelier.io.types import ArrayOptions, ImportFormat, ImportOptions, MediaOptions
from datelier.pipeline.editing import DatasetEditor
from datelier.plotting.selection import LinkedSelection
from datelier.workspace.jobs import WorkspaceJobs
from datelier.workspace.restore import RestoredWorkspace
from datelier.workspace.session_restore import RestoredSessionFile
from datelier.workspace.session_types import SourceDraft
from datelier.workspace.types import WorkspaceViews


class FileController:
    def __init__(
        self,
        executor: Executor,
        *,
        identity: str | None = None,
        loader: DatasetLoader | None = None,
        array_store: ArrayStore | None = None,
        playback: AudioPlayback | None = None,
    ) -> None:
        self.identity = identity or uuid4().hex
        self.view_name = ""
        self.closed = False
        self.loader = loader or DatasetLoader(executor=executor)
        self.pages = PreviewCache(executor=executor)
        self.editor = DatasetEditor(executor=executor)
        self.exporter = DatasetExporter(executor=executor)
        self.explorer = Explorer(executor=executor)
        self.selection = LinkedSelection()
        self.table = TableController(self.pages, self.selection)
        self.profiles = ProfileController(self.explorer)
        self.workspace = WorkspaceJobs(executor=executor)
        self.runtime = DatasetRuntime(
            self.loader,
            self.pages,
            self.editor,
            self.exporter,
            self.explorer,
            self.selection,
            self.workspace,
        )
        self.schema = SchemaController(self.editor.request)
        self.plots = PlotState()
        self.views = WorkspaceViews()
        self.analysis = AnalysisController(
            jobs=AnalysisJobs(executor=executor), plots=AnalysisPlots(executor=executor)
        )
        self.records = RecordController(self.selection, executor)
        self.references = ReferenceJobs(executor)
        self.reference_tools = ReferenceController(self.references)
        self.arrays = ArrayJobs(executor, store=array_store)
        self.checkpoints = CheckpointJobs(executor)
        self.text = TextController(executor)
        self.images = ImageController(executor)
        self.audio = AudioController(executor, playback)
        self.record_views = RecordViews(executor, self.audio.player)
        self.objects = ObjectController(self.record_views)
        self.array_source = NumericSourceController(self.arrays)
        self.tensor_source = NumericSourceController(self.checkpoints)
        self.array_records = ArrayRecordController(executor, self.arrays.store)
        self.array_record_source = NumericSourceController(self.array_records.jobs)
        self.recovery: RestoredSessionFile | None = None
        self.draft: SourceDraft | None = None
        self.imports = ImportController(self._request_import)
        self.choices: tuple[ColumnChoice, ...] = ()
        self._plot_settings: PlotSettings | None = None

    @property
    def inspection(self) -> Inspection | None:
        return self.loader.active

    @property
    def title(self) -> str:
        source = (
            self.inspection.dataset.source.path
            if self.inspection
            else self.loader.status.path
        )
        return self.view_name or (source.name if source else "Untitled")

    def open(
        self,
        path: Path,
        options: ImportOptions | None = None,
        *,
        format: ImportFormat | None = None,
    ) -> None:
        self.draft = import_draft(path, options, format)
        self.imports.bind(self.draft)
        self.loader.request(path, options, format=format)
        self.imports.busy = True

    def _request_import(self, draft: SourceDraft) -> None:
        automatic = (
            self.imports.format is None and draft.options == DEFAULTS[draft.format]()
        )
        self.open(
            Path(draft.path),
            None if automatic else draft.options,
            format=None if automatic else draft.format,
        )

    def media_input(self) -> MediaInput:
        return MediaInput(
            self.identity,
            self.view_name,
            self.inspection,
            self.references.settings,
            self.references.index,
            tuple(sorted(self.selection.row_ids)),
            self.arrays.store,
            self.records.settings,
            self.records.jobs.active,
        )

    def install(self, restored: RestoredWorkspace) -> None:
        self.runtime.install(restored)
        self.views = replace(
            restored.workspace.views,
            tab="Relationships"
            if restored.workspace.views.tab == "Scatter"
            else restored.workspace.views.tab,
        )
        self.records.settings = self.views.inspect
        self.text.jobs.settings = self.views.text
        self.text.original_height = self.views.text_height
        self.text.token_height = self.views.token_height
        self.text.profile_tab = self.views.text_profile_tab
        self.images.settings = self.views.image
        self.audio.settings = self.views.audio
        self.references.settings = self.views.references
        self.reference_tools.thumbnails = self.views.thumbnails
        self.table.presentation.restore(self.views.presentation)
        imported = restored.inspection.imported
        if imported.array_catalog is not None:
            self.arrays.bind(
                imported.array_catalog, restored.inspection.dataset.revision
            )
        self.arrays.settings = self.views.array_slice or SliceSettings()
        self.arrays.store.limit = self.views.array_retention_bytes
        if imported.checkpoint_catalog is not None:
            self.checkpoints.bind(
                imported.checkpoint_catalog, restored.inspection.dataset.revision
            )
        self.checkpoints.settings = self.views.checkpoint_slice or SliceSettings()
        self.checkpoints.store.limit = self.views.checkpoint_retention_bytes
        self.array_source.sync(self.arrays.catalog)
        self.tensor_source.sync(self.checkpoints.catalog)
        self.array_source.height = self.views.array_height
        self.array_record_source.height = self.views.array_record_height
        self.array_records.jobs.settings = (
            self.views.array_record_slice or SliceSettings()
        )
        self.tensor_source.height = self.views.checkpoint_height
        self.array_source.retention_mib = self.array_record_source.retention_mib = (
            self.arrays.store.limit // (1024 * 1024)
        )
        self.tensor_source.retention_mib = self.checkpoints.store.limit // (1024 * 1024)
        if self.views.array_member_mode is not None:
            self.array_source.member_mode = self.views.array_member_mode
        if self.views.checkpoint_member_mode is not None:
            self.tensor_source.member_mode = self.views.checkpoint_member_mode
        self._bind()
        restore_plots(self.plots, restored.inspection.dataset, restored.workspace.plots)
        if self.views.scatter_dimensions is not None:
            self.plots.three_d = self.views.scatter_dimensions == 3
        restore_analysis(
            self.analysis.controls, restored.workspace, restored.inspection.dataset
        )
        self.profiles.restore_selection(
            restored.inspection.dataset, self.views.profile_selection
        )
        if self.plots.profile_redirect and self.views.tab == "Relationships":
            self.profiles.choose((self.plots.profile_redirect,))
            self.views = replace(self.views, tab="Profiles")
        self.profiles.height = self.views.profile_height
        self.profiles.mode = self.views.profile_mode
        self.profiles.text = self.views.profile_text
        self.analysis.source = self.views.coordinate_source
        self.plots.choose_color(self.views.color_source or self.plots.color_source)
        self.table.refresh(self.inspection)
        self.table.column_start = self.views.column_start
        self.table.target_row = self.views.target_row
        self.table.jump = True

    def _bind(self) -> None:
        active = self.inspection
        if active is None:
            return
        dataset = active.dataset
        self.draft = SourceDraft(
            str(dataset.source.path), active.imported.format, active.imported.options
        )
        self.imports.bind(self.draft)
        self.plots.bind(dataset)
        self.analysis.controls.bind(dataset)
        self.choices = tuple(
            ColumnChoice(info.name, info.role.value, info.role == ColumnRole.NUMERIC)
            for info in dataset.roles or ()
        )
        primary = self.records.settings.primary
        if primary not in dataset.table.columns:
            primary = next(
                (
                    c.name
                    for c in self.choices
                    if dataset.role(c.name).role
                    in (
                        ColumnRole.IMAGE,
                        ColumnRole.AUDIO,
                        ColumnRole.EXTERNAL_TEXT,
                        ColumnRole.TEXT,
                        ColumnRole.LIST_TEXT,
                    )
                ),
                next(iter(dataset.table.columns), None),
            )
        if (
            isinstance(active.imported.options, MediaOptions)
            and active.imported.options.text_lines
            and "text" in dataset.table.columns
        ):
            primary = "text"
        self.records.settings = replace(self.records.settings, primary=primary)
        if self.text.jobs.settings.column not in dataset.table.columns:
            self.text.jobs.settings = replace(
                self.text.jobs.settings,
                column=next(
                    iter(
                        sorted(
                            (
                                n
                                for n, dtype in dataset.table.schema.items()
                                if is_text_field(dtype)
                            ),
                            key=lambda name: (
                                name != "text",
                                dataset.role(name).role
                                not in (ColumnRole.TEXT, ColumnRole.LIST_TEXT),
                            ),
                        )
                    ),
                    None,
                ),
            )
        self._plot_settings = None

    def open_analysis_result(self, algorithm: Algorithm) -> None:
        result = self.analysis.jobs.results.get(algorithm)
        if result is None or self.loader.revision != result.revision:
            return
        if algorithm.is_clustering:
            self.plots.choose_color(algorithm.value)
            self.plots.choose_chart(
                "Scatter 3D" if self.plots.three_d else "Scatter 2D"
            )
        else:
            self.analysis.source = algorithm
            self.plots.choose_chart(
                "Scatter 3D"
                if isinstance(result, EmbeddingResult) and result.values.shape[1] == 3
                else "Scatter 2D"
            )
        self.analysis.pending_result = None
        self.views = replace(self.views, tab="Relationships")

    def poll(self) -> None:
        if self.closed:
            return
        changes = self.runtime.poll()
        if changes.restored:
            self.install(changes.restored)
        if changes.loaded:
            self.record_views.clear()
            self.recovery = None
        self.imports.busy = self.loader.status.phase == LoadPhase.LOADING
        self.imports.blocked = self.recovery is not None
        if changes.loaded or changes.edited:
            self._bind()
            if changes.loaded and self.inspection:
                if self.inspection.imported.format == ImportFormat.MEDIA:
                    self.views = replace(self.views, tab="Inspect")
        active = self.inspection
        dataset = active.dataset if active else None
        self.analysis.sync_dimensions(self.plots)
        self.analysis.poll(dataset)
        self.analysis.sync_colors(self.plots)
        result = (
            self.analysis.jobs.results.get(self.analysis.source)
            if self.analysis.source is not None
            else None
        )
        if dataset is not None and isinstance(result, EmbeddingResult):
            if result.revision == dataset.revision:
                self.analysis.plots.ensure(
                    dataset,
                    result,
                    self.plots.point_limit,
                    self.plots.color_column,
                    self.plots.cluster_result if self.plots.cluster_color else None,
                )
        if (
            dataset is None
            or not isinstance(result, EmbeddingResult)
            or result.revision != dataset.revision
        ):
            self.analysis.plots.clear()
        try:
            settings = self.plots.settings()
            if dataset is not None and settings != self._plot_settings:
                self.explorer.request(dataset, settings)
                self._plot_settings = settings
            self.plots.error = ""
        except ValueError as error:
            self.plots.error = str(error)
        self.runtime.poll_prepared()
        self.table.refresh(active)
        self.reference_tools.sync(self.table.reference_columns)
        self.profiles.poll(active, self.choices)
        if active and any(
            c.role in REFERENCE_ROLES for c in active.dataset.roles or ()
        ):
            self.references.bind(
                active.dataset.source.path,
                active.dataset.revision,
                discover_nearby=active.imported.format != ImportFormat.MEDIA,
            )
        elif self.references.source is not None:
            self.references.unbind()
        self.references.poll()
        self.records.poll(active)
        if active and active.imported.array_catalog:
            self.arrays.bind(active.imported.array_catalog, active.dataset.revision)
        elif self.arrays.catalog and self.recovery is None:
            self.arrays.unbind()
        self.arrays.poll()
        if active and active.imported.checkpoint_catalog:
            self.checkpoints.bind(
                active.imported.checkpoint_catalog, active.dataset.revision
            )
        elif self.checkpoints.catalog:
            self.checkpoints.unbind()
        self.checkpoints.poll()
        self.objects.sync(active.imported.object_root if active else None)
        self.array_source.sync(self.arrays.catalog)
        self.array_record_source.sync(self.arrays.catalog)
        if (
            changes.loaded
            and active
            and isinstance(active.imported.options, ArrayOptions)
            and active.imported.options.mapping is not None
        ):
            self.array_source.member_mode = False
            self.views = replace(self.views, tab="Inspect")
            self.records.settings = replace(self.records.settings, gallery=False)
        self.tensor_source.sync(self.checkpoints.catalog)
        media = self.media_input()
        for controller in (self.text, self.images, self.audio, self.array_records):
            controller.sync(media)
        self.schema.refresh(active, busy=self.editor.busy)
        self.record_views.poll(self)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.imports.close()
        self.record_views.close()
        self.audio.close(self.identity)
        for controller in (
            self.records,
            self.array_records,
            self.text,
            self.images,
            self.references,
            self.arrays,
            self.checkpoints,
        ):
            controller.close()
        self.analysis.close(wait=False)
        self.runtime.close()
        self.schema.refresh(None, busy=False)
        self.objects.sync(None)
        self.array_source.sync(None)
        self.tensor_source.sync(None)
        self.array_record_source.sync(None)
