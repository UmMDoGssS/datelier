"""Tabular inspection workbench; frames consume prepared state only."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from imgui_bundle import hello_imgui, imgui, immapp

from datelier.editing import DatasetEditor
from datelier.exploration import Explorer
from datelier.exporting import DatasetExporter
from datelier.gui_controls import ImportControls, show_schema
from datelier.gui_exploration import ExplorationView
from datelier.gui_export import ExportControls
from datelier.gui_operations import OperationControls
from datelier.gui_plot_controls import PlotControls
from datelier.gui_table import TableView
from datelier.loading import DatasetLoader, LoadPhase
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
        show_schema(loader)

    def explore() -> None:
        plot_controls.show(explorer, loader.active.dataset if loader.active else None)
        exploration.show(
            explorer,
            selection,
            view,
            plot_controls,
            loader.active.dataset if loader.active else None,
        )

    left = hello_imgui.DockingSplit()
    left.initial_dock = "MainDockSpace"
    left.new_dock = "ImportSpace"
    left.direction = imgui.Dir.left
    left.ratio = 0.3
    lower = hello_imgui.DockingSplit()
    lower.initial_dock = "ImportSpace"
    lower.new_dock = "SchemaSpace"
    lower.direction = imgui.Dir.down
    lower.ratio = 0.55
    edits = hello_imgui.DockingSplit()
    edits.initial_dock = "MainDockSpace"
    edits.new_dock = "EditSpace"
    edits.direction = imgui.Dir.right
    edits.ratio = 0.32
    plots = hello_imgui.DockingSplit()
    plots.initial_dock = "MainDockSpace"
    plots.new_dock = "PlotSpace"
    plots.direction = imgui.Dir.down
    plots.ratio = 0.58
    params.docking_params.docking_splits = [left, lower, edits, plots]
    windows = []
    for label, space, callback in (
        ("Explore", "PlotSpace", explore),
        ("Open dataset", "ImportSpace", lambda: controls.show(loader)),
        ("Table preview", "MainDockSpace", show_table),
        ("Schema and nulls", "SchemaSpace", schema),
        (
            "Transform and history",
            "EditSpace",
            lambda: operations.show(
                editor,
                loading=loader.status.phase == LoadPhase.LOADING or exporter.busy,
            ),
        ),
        (
            "Export table",
            "EditSpace",
            lambda: exports.show(
                editor, exporter, loading=loader.status.phase == LoadPhase.LOADING
            ),
        ),
    ):
        window = hello_imgui.DockableWindow()
        window.label = label
        window.dock_space_name = space
        window.gui_function = callback
        windows.append(window)
    params.docking_params.dockable_windows = windows
    load_started = perf_counter()
    previous_frame = load_started
    if initial_path:
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
            plot_controls.bind(loader.active.dataset)
            selection.bind(loader.active.dataset.revision)
            explorer.request(loader.active.dataset, plot_controls.settings())
        if loader.status.phase == LoadPhase.LOADING:
            editor.abandon()
        edited = editor.poll(loader.revision)
        if edited is not None:
            loader.active = edited
            pages.bind(edited)
            view.reset()
            plot_controls.bind(edited.dataset)
            selection.bind(edited.dataset.revision)
            explorer.request(edited.dataset, plot_controls.settings())
        explorer.poll(loader.revision)
        exporter.poll()
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
        immapp.run(params, addons)
    finally:
        loader.close()
        pages.close()
        editor.close()
        exporter.close()
        explorer.close()
    return evidence
