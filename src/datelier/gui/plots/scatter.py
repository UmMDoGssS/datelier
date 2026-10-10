"""Bounded 2D scatter drawing and gestures shared by raw/reduced plots."""

from dataclasses import dataclass, field

import numpy as np
from imgui_bundle import imgui, implot

from datelier.gui.components.help import show_help
from datelier.gui.data.table import TableView
from datelier.gui.plots.area import PlotArea
from datelier.gui.plots.axes import AxisControls
from datelier.gui.plots.scatter3d import Scatter3DView
from datelier.gui.plots.scatter_items import draw_color_items, with_color_scale
from datelier.gui.plots.selection import ScatterInteraction
from datelier.plotting.data import Scatter
from datelier.plotting.selection import LinkedSelection


def draw_scatter(
    points: Scatter,
    selection: LinkedSelection,
    table: TableView,
    interaction: ScatterInteraction,
    fit: bool,
    height: float,
    axes: AxisControls | None = None,
    *,
    width: float = -1,
) -> bool:
    if fit:
        implot.set_next_axes_to_fit()
    shown = implot.begin_plot("Scatter 2D", (width, height))
    if shown:
        implot.setup_axes(points.x_name, points.y_name)
        if axes is not None:
            axes.apply()
        selected = (
            np.isin(points.row_ids, tuple(selection.row_ids))
            if points.revision == selection.revision
            else np.zeros(len(points.x), dtype=bool)
        )
        visible = draw_color_items(points, selected)
        interaction.show(points, selection, table, visible=visible)
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
            lambda height, fit, axes: with_color_scale(
                points,
                height,
                lambda width: (
                    self.scatter3d.show(
                        points, selection, table, fit, height, width=width
                    )
                    if three_d
                    else draw_scatter(
                        points,
                        selection,
                        table,
                        self.interaction,
                        fit,
                        height,
                        axes,
                        width=width,
                    )
                ),
            ),
            numeric_axes=(False, False) if three_d else (True, True),
            three_d=three_d,
        )
        if shown:
            self.fit = False
            self.frames += 1
        if points.colors is not None and points.colors.note:
            imgui.text_wrapped(points.colors.note)
        show_help(
            "3D: right-drag rotates, left-drag pans, wheel zooms. Click "
            "selects; Ctrl-click toggles; Shift-drag brushes projected "
            "displayed points."
            if three_d
            else "Wheel zooms; middle-drag pans; double-click fits. Click "
            "selects; Ctrl-click toggles; Shift-drag brushes displayed "
            "points."
        )
        return shown
