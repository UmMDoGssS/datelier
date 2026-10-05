"""Tabular inspection workbench; frames consume prepared state only."""

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from imgui_bundle import hello_imgui, imgui, immapp

from datelier.editing import DatasetEditor
from datelier.exploration import Explorer
from datelier.exporting import DatasetExporter
from datelier.gui_analysis import AnalysisSession
from datelier.gui_controls import ImportControls, show_schema
from datelier.gui_exploration import ExplorationView
from datelier.gui_export import ExportControls
from datelier.gui_layout import configure_layout
from datelier.gui_operations import OperationControls
from datelier.gui_plot_controls import PlotControls
from datelier.gui_preferences import PreferenceControls
from datelier.gui_table import TableView
from datelier.gui_workspace import WorkspaceControls
from datelier.gui_workspace_state import (
    restore_plots,
    restore_view_settings,
    restore_views,
)
from datelier.loading import DatasetLoader, LoadPhase, LoadStatus
from datelier.preferences import preference_path
from datelier.preview import PreviewCache
from datelier.selection import LinkedSelection


@dataclass
class GuiSession:
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
    preferences: PreferenceControls


@dataclass
class InspectionEvidence:
    frames: int = 0
    loading_frames: int = 0
    failed_frames: int = 0
    first_preview_ms: float | None = None
    max_rendered_rows: int = 0
    table_dock_id: int = 0
    schema_dock_id: int = 0
    frame_intervals_ms: list[float] = field(default_factory=list)


def run_gui(
    initial_path: Path | None = None,
    *,
    smoke_frames: int = 0,
    on_frame: Callable[[GuiSession, InspectionEvidence], None] | None = None,
    dataset_loader: DatasetLoader | None = None,
    initial_workspace: Path | None = None,
    preferences_path: Path | None = None,
) -> InspectionEvidence:
    if smoke_frames < 0:
        raise ValueError("Smoke frame count must be nonnegative")
    loader = dataset_loader if dataset_loader is not None else DatasetLoader()
    pages = PreviewCache()
    view = TableView()
    controls = ImportControls(path=str(initial_path) if initial_path else "")
    editor = DatasetEditor()
    operations = OperationControls()
    exporter = DatasetExporter()
    exports = ExportControls()
    explorer = Explorer()
    exploration = ExplorationView()
    plot_controls = PlotControls()
    selection = LinkedSelection()
    analysis = AnalysisSession()
    workspace = WorkspaceControls(
        path=str(initial_workspace) if initial_workspace else ""
    )
    preferences = PreferenceControls(
        preferences_path
        if preferences_path is not None
        else (preference_path() if not smoke_frames else None)
    )
    session = GuiSession(
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
    )
    evidence = InspectionEvidence()
    params = hello_imgui.RunnerParams()
    params.app_window_params.window_title = "Datelier — data inspection"
    params.app_window_params.window_geometry.size = (1280, 800)
    params.ini_disable = True
    params.fps_idling.enable_idling = False
    params.imgui_window_params.default_imgui_window_type = (
        hello_imgui.DefaultImGuiWindowType.provide_full_screen_dock_space
    )

    def show_table() -> None:
        evidence.table_dock_id = imgui.get_window_dock_id()
        view.show(loader.active, pages, selection)
        evidence.max_rendered_rows = max(evidence.max_rendered_rows, view.rendered_rows)
        if view.prepared_visible_rows and evidence.first_preview_ms is None:
            evidence.first_preview_ms = (perf_counter() - load_started) * 1000

    def schema() -> None:
        evidence.schema_dock_id = imgui.get_window_dock_id()
        show_schema(loader, editor)

    def explore() -> None:
        plot_controls.show(explorer, loader.active.dataset if loader.active else None)
        exploration.show(
            explorer,
            selection,
            view,
            plot_controls,
            loader.active.dataset if loader.active else None,
            analysis,
        )

    configure_layout(
        params,
        {
            "Explore": explore,
            "Open dataset": lambda: controls.show(loader),
            "Workspace": lambda: workspace.show(session),
            "Table preview": show_table,
            "Schema and nulls": schema,
            "Analysis": lambda: analysis.show_panel(
                loader.active.dataset if loader.active else None,
                plot_controls,
            ),
            "Transform and history": lambda: operations.show(
                editor,
                loading=loader.status.phase == LoadPhase.LOADING
                or exporter.busy
                or workspace.jobs.busy,
            ),
            "Export table": lambda: exports.show(
                editor,
                exporter,
                loading=loader.status.phase == LoadPhase.LOADING or workspace.jobs.busy,
            ),
        },
    )
    # Configure this before runner initialization: the default builder otherwise
    # replaces saved docking even when ini settings are loaded before a frame.
    if preferences.value.layout:
        params.docking_params.layout_condition = (
            hello_imgui.DockingLayoutCondition.never
        )
    params.imgui_window_params.show_menu_bar = True
    params.imgui_window_params.show_menu_view_themes = False
    params.callbacks.setup_imgui_style = preferences.apply_theme
    params.callbacks.post_init = lambda: preferences.before_frame(params)
    params.callbacks.pre_new_frame = lambda: preferences.before_frame(params)
    params.callbacks.show_menus = lambda: preferences.show_menu(session, params)
    params.callbacks.before_exit = lambda: preferences.save(session, params)
    load_started = perf_counter()
    previous_frame = load_started
    if initial_workspace:
        workspace.open(session)
    elif initial_path:
        loader.request(initial_path)

    def frame() -> None:
        nonlocal previous_frame
        now = perf_counter()
        if smoke_frames and evidence.frames >= 10:
            evidence.frame_intervals_ms.append((now - previous_frame) * 1000)
        previous_frame = now
        evidence.frames += 1
        if loader.poll():
            assert loader.active is not None
            editor.bind(loader.active)
            pages.bind(loader.active)
            view.reset()
            analysis.controls.bind(loader.active.dataset)
            restore_plots(plot_controls, loader.active.dataset, preferences.value.plots)
            restore_view_settings(session, preferences.value.views)
            selection.bind(loader.active.dataset.revision)
            explorer.request(loader.active.dataset, plot_controls.settings())
        if loader.status.phase == LoadPhase.LOADING:
            editor.abandon()
            workspace.jobs.abandon()
        restored = workspace.jobs.poll(loader.revision)
        if restored is not None:
            loader.active = restored.inspection
            loader.status = LoadStatus(
                LoadPhase.READY, restored.pipeline.source.source.path
            )
            editor.bind(restored.inspection)
            editor.pipeline = restored.pipeline
            pages.bind(restored.inspection)
            view.reset()
            adjusted = restore_views(session, restored.workspace)
            if adjusted:
                workspace.jobs.message += (
                    " Saved plot settings were adjusted"
                    " to the current columns and charts."
                )
            selection.bind(restored.inspection.dataset.revision)
            explorer.request(restored.inspection.dataset, plot_controls.settings())
        edited = editor.poll(loader.revision)
        if edited is not None:
            loader.active = edited
            pages.bind(edited)
            view.reset()
            analysis.controls.bind(edited.dataset)
            plot_controls.bind(edited.dataset)
            selection.bind(edited.dataset.revision)
            explorer.request(edited.dataset, plot_controls.settings())
        analysis.sync_dimensions(plot_controls)
        completed = analysis.poll(loader.active.dataset if loader.active else None)
        if completed:
            exploration.tab = "Relationships"
            plot_controls.relationship_chart = "Scatter"
        if analysis.sync_colors(plot_controls) and loader.active is not None:
            explorer.request(loader.active.dataset, plot_controls.settings())
        explorer.poll(loader.revision)
        exporter.poll()
        preferences.poll()
        pages.poll()
        if loader.status.phase == LoadPhase.LOADING:
            evidence.loading_frames += 1
        elif loader.status.phase == LoadPhase.FAILED:
            evidence.failed_frames += 1
        if on_frame:
            on_frame(session, evidence)
        if smoke_frames and evidence.frames >= smoke_frames:
            hello_imgui.get_runner_params().app_shall_exit = True

    params.callbacks.show_gui = frame
    try:
        addons = immapp.AddOnsParams()
        addons.with_implot = True
        addons.with_implot3d = True
        immapp.run(params, addons)
    finally:
        loader.close()
        pages.close()
        editor.close()
        exporter.close()
        explorer.close()
        analysis.close()
        workspace.jobs.close()
        preferences.close()
        if preferences.message.startswith("Preferences failed:"):
            print(preferences.message, file=sys.stderr)
    return evidence
