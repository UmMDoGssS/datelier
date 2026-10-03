from dataclasses import dataclass, field
from time import perf_counter

import polars as pl
from imgui_bundle import hello_imgui, imgui, immapp, implot

from datelier.feasibility.plot_data import DEFAULT_POINT_LIMIT, prepare_scatter


@dataclass
class GuiEvidence:
    frames: int = 0
    plot_frames: int = 0
    preview_dock_id: int = 0
    plot_dock_id: int = 0
    frame_intervals_ms: list[float] = field(default_factory=list)


def run_gui(
    table: pl.DataFrame,
    *,
    smoke_frames: int = 0,
    point_limit: int = DEFAULT_POINT_LIMIT,
) -> GuiEvidence:
    """Render prepared synthetic data, optionally exit after a bounded smoke run."""
    if smoke_frames < 0:
        raise ValueError("Smoke frame count must be nonnegative")
    points = prepare_scatter(table, "feature_0", "feature_1", limit=point_limit)
    scatter_style = implot.Spec()
    scatter_style.marker_size = 2
    scatter_style.line_weight = 0
    columns = ("row_id", "feature_0", "feature_1", "category")
    preview = tuple(
        tuple(
            f"{value:.4f}" if isinstance(value, float) else str(value) for value in row
        )
        for row in table.select(columns).head(12).iter_rows()
    )
    evidence = GuiEvidence()
    params = hello_imgui.RunnerParams()
    params.app_window_params.window_title = "Datelier — stack feasibility"
    params.app_window_params.window_geometry.size = (1100, 700)
    params.ini_disable = True
    params.fps_idling.enable_idling = False
    params.imgui_window_params.default_imgui_window_type = (
        hello_imgui.DefaultImGuiWindowType.provide_full_screen_dock_space
    )

    def show_preview() -> None:
        evidence.preview_dock_id = imgui.get_window_dock_id()
        imgui.text(f"Synthetic fixture: {table.height:,} rows, {table.width} columns")
        imgui.text("First 12 rows, 4 columns; full table remains in Polars.")
        if imgui.begin_table("preview", len(columns), imgui.TableFlags_.borders):
            for name in columns:
                imgui.table_setup_column(name)
            imgui.table_headers_row()
            for row in preview:
                imgui.table_next_row()
                for column, value in enumerate(row):
                    imgui.table_set_column_index(column)
                    imgui.text_unformatted(value)
            imgui.end_table()

    def show_plot() -> None:
        evidence.plot_dock_id = imgui.get_window_dock_id()
        imgui.text(
            f"First {len(points.x):,} of {points.eligible_rows:,} finite rows "
            f"({points.source_rows:,} total)"
        )
        imgui.text("Drag tabs to rearrange; use plot axes to zoom and pan.")
        if implot.begin_plot("Selected Polars coordinates", (-1, -1)):
            implot.setup_axes(points.x_name, points.y_name)
            implot.plot_scatter("Synthetic rows", points.x, points.y, scatter_style)
            implot.end_plot()
            evidence.plot_frames += 1

    split = hello_imgui.DockingSplit()
    split.initial_dock = "MainDockSpace"
    split.new_dock = "PreviewSpace"
    split.direction = imgui.Dir.left
    split.ratio = 0.4
    preview_window = hello_imgui.DockableWindow()
    preview_window.label = "Table preview"
    preview_window.dock_space_name = "PreviewSpace"
    preview_window.gui_function = show_preview
    plot_window = hello_imgui.DockableWindow()
    plot_window.label = "Scatter plot"
    plot_window.dock_space_name = "MainDockSpace"
    plot_window.gui_function = show_plot
    params.docking_params.docking_splits = [split]
    params.docking_params.dockable_windows = [preview_window, plot_window]
    previous_frame = perf_counter()

    def on_frame() -> None:
        nonlocal previous_frame
        now = perf_counter()
        if smoke_frames and evidence.frames >= 10:
            evidence.frame_intervals_ms.append((now - previous_frame) * 1000)
        previous_frame = now
        evidence.frames += 1
        if smoke_frames and evidence.frames >= smoke_frames:
            hello_imgui.get_runner_params().app_shall_exit = True

    params.callbacks.show_gui = on_frame
    addons = immapp.AddOnsParams()
    addons.with_implot = True
    immapp.run(params, addons)
    return evidence
