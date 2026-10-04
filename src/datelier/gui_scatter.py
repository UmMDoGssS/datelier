"""Bounded 2D scatter drawing and gestures shared by raw/reduced plots."""

import numpy as np
from imgui_bundle import imgui, implot

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
) -> bool:
    if fit:
        implot.set_next_axes_to_fit()
    style = implot.Spec()
    style.marker_size = 2
    style.marker = implot.Marker_.square
    style.line_weight = 0
    height = max(150, min(220, imgui.get_content_region_avail().y - 5))
    shown = implot.begin_plot("Scatter", (-1, height))
    if shown:
        implot.setup_axes(points.x_name, points.y_name)
        xs, ys = selection.unselected(points)
        if points.colors is not None:
            mask = ~np.isin(points.row_ids, tuple(selection.row_ids))
            style.marker_fill_colors = points.colors.rgba[mask]
            style.marker_line_colors = points.colors.rgba[mask]
        if len(xs):
            implot.plot_scatter("Rows", xs, ys, style)
        interaction.show(points, selection, table)
        implot.end_plot()
    return shown
