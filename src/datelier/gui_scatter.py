"""Bounded 2D scatter drawing and gestures shared by raw/reduced plots."""

from dataclasses import dataclass, field

import numpy as np
from imgui_bundle import imgui, implot

from datelier.gui_axes import AxisControls
from datelier.gui_plot_area import PlotArea
from datelier.gui_scatter3d import Scatter3DView
from datelier.gui_selection import ScatterInteraction
from datelier.gui_table import TableView
from datelier.plotting import Scatter
from datelier.selection import LinkedSelection


def draw_scatter(
    points: Scatter,
    selection: LinkedSelection,
    table: TableView,
    interaction: ScatterInteraction,
    fit: bool,
    height: float,
    axes: AxisControls | None = None,
) -> bool:
    if fit:
        implot.set_next_axes_to_fit()
    style = implot.Spec()
    style.marker_size = 2
    style.marker = implot.Marker_.square
    style.line_weight = 0
    shown = implot.begin_plot("Scatter", (-1, height))
    if shown:
        implot.setup_axes(points.x_name, points.y_name)
        if axes is not None:
            axes.apply()
        xs, ys = selection.unselected(points)
        if points.colors is not None:
            mask = ~np.isin(points.row_ids, tuple(selection.row_ids))
            style.marker_fill_colors = points.colors.rgba[mask]
            style.marker_line_colors = points.colors.rgba[mask]
        if len(xs):
            implot.plot_scatter("Rows", xs, ys, style)
        interaction.show(points, selection, table)
        if axes is not None:
            axes.observe()
        implot.end_plot()
    return shown


@dataclass
class ScatterView:
    area: PlotArea = field(default_factory=PlotArea)
    area3d: PlotArea = field(default_factory=PlotArea)
    scatter3d: Scatter3DView = field(default_factory=Scatter3DView)
    interaction: ScatterInteraction = field(default_factory=ScatterInteraction)
    fit: bool = False
    frames: int = 0

    def show(
        self,
        points: Scatter,
        selection: LinkedSelection,
        table: TableView,
        three_d: bool,
        *,
        embedding: bool = False,
    ) -> bool:
        summary = (
            f"{len(points.x):,} / {points.eligible_rows:,} rows"
            if len(points.x) < points.eligible_rows
            else f"{len(points.x):,} {'fitted rows' if embedding else 'rows'}"
        )
        if not embedding and points.total_rows > points.eligible_rows:
            summary += f" · {points.total_rows - points.eligible_rows:,} excluded"
        if selection.row_ids:
            summary += f" · {len(selection.row_ids):,} selected"
        imgui.text_wrapped(summary)
        if selection.row_ids:
            imgui.same_line()
            if imgui.get_content_region_avail().x < 60:
                imgui.new_line()
            if imgui.button("Clear"):
                selection.choose(points.revision, ())
        if points.colors is not None:
            if imgui.collapsing_header("Color legend"):
                imgui.text_wrapped(points.colors.note)
                for label, rgba in points.colors.legend:
                    color = imgui.ImVec4(
                        (rgba & 255) / 255,
                        ((rgba >> 8) & 255) / 255,
                        ((rgba >> 16) & 255) / 255,
                        1,
                    )
                    imgui.text_colored(color, label)
                    imgui.same_line()
                imgui.new_line()
        key = (
            points.revision,
            points.x_name,
            points.y_name,
            points.z_name,
            three_d,
        )
        area = self.area3d if three_d else self.area
        if self.fit:
            area.fit = True
        shown = area.show(
            "Scatter 3D plot" if three_d else "Scatter 2D plot",
            key,
            lambda height, fit, axes: (
                self.scatter3d.show(points, selection, table, fit, height)
                if three_d
                else draw_scatter(
                    points, selection, table, self.interaction, fit, height, axes
                )
            ),
            numeric_axes=(False, False) if three_d else (True, True),
            three_d=three_d,
        )
        if shown:
            self.fit = False
            self.frames += 1
        if imgui.collapsing_header("Details##scatter"):
            if three_d:
                imgui.text_wrapped(
                    "3D: right-drag rotates, left-drag pans, wheel zooms. "
                    "Click selects; Ctrl-click toggles; "
                    "Shift-drag brushes projected displayed points."
                )
            imgui.text_wrapped(
                "2D wheel: zoom · middle-drag: pan · double-click: fit. "
                "Click: select · Ctrl-click: toggle · "
                "Shift-drag: brush displayed points."
            )
        return shown
