"""Scatter input and overlays; all interaction work is bounded by displayed points."""

from dataclasses import dataclass

import numpy as np
from imgui_bundle import imgui, implot

from datelier.gui_table import TableView
from datelier.plotting import Scatter
from datelier.projection import projected_nearest
from datelier.selection import LinkedSelection


@dataclass
class ScatterInteraction:
    point_pixel: tuple[float, float] = (0, 0)
    center_pixel: tuple[float, float] = (0, 0)
    limits: tuple[float, float, float, float] = (0, 0, 0, 0)
    selected_points: int = 0
    brush_start: tuple[float, float] | None = None
    _points: Scatter | None = None

    def show(
        self, points: Scatter, selection: LinkedSelection, table: TableView
    ) -> None:
        if points is not self._points:
            self.brush_start = None
            self._points = points
        # Reserve left-click for row selection and Shift-left-drag for brushing.
        implot.get_input_map().pan = imgui.MouseButton_.middle
        bounds = implot.get_plot_limits()
        self.limits = (bounds.x.min, bounds.x.max, bounds.y.min, bounds.y.max)
        pos, size = implot.get_plot_pos(), implot.get_plot_size()
        self.center_pixel = (pos.x + size.x / 2, pos.y + size.y / 2)
        if len(points.x):
            middle = len(points.x) // 2
            pixel = implot.plot_to_pixels(
                float(points.x[middle]), float(points.y[middle])
            )
            self.point_pixel = (pixel.x, pixel.y)
        mouse = implot.get_plot_mouse_pos()
        if implot.is_plot_hovered() and imgui.is_mouse_clicked(imgui.MouseButton_.left):
            if imgui.get_io().key_shift:
                self.brush_start = (mouse.x, mouse.y)
            else:
                pixels = np.array(
                    [
                        (p.x, p.y)
                        for p in (
                            implot.plot_to_pixels(float(x), float(y))
                            for x, y in zip(points.x, points.y, strict=True)
                        )
                    ],
                    dtype=np.float64,
                ).reshape(-1, 2)
                visible = (
                    (pixels[:, 0] >= pos.x)
                    & (pixels[:, 0] <= pos.x + size.x)
                    & (pixels[:, 1] >= pos.y)
                    & (pixels[:, 1] <= pos.y + size.y)
                )
                pixels[~visible] = np.nan
                screen = imgui.get_io().mouse_pos
                index = projected_nearest(
                    pixels, np.zeros(len(pixels)), (screen.x, screen.y)
                )
                if index is not None and selection.choose(
                    points.revision,
                    (int(points.row_ids[index]),),
                    toggle=imgui.get_io().key_ctrl,
                ):
                    table.target_row, table.jump = (
                        int(points.positions[index]) + 1,
                        True,
                    )
        if self.brush_start is not None:
            start = implot.plot_to_pixels(*self.brush_start)
            end = implot.plot_to_pixels(mouse.x, mouse.y)
            implot.push_plot_clip_rect()
            implot.get_plot_draw_list().add_rect(
                imgui.ImVec2(min(start.x, end.x), min(start.y, end.y)),
                imgui.ImVec2(max(start.x, end.x), max(start.y, end.y)),
                imgui.get_color_u32(imgui.ImVec4(1, 0.7, 0.2, 1)),
            )
            implot.pop_plot_clip_rect()
            if imgui.is_mouse_released(imgui.MouseButton_.left):
                selection.rectangle(points, *self.brush_start, mouse.x, mouse.y)
                self.brush_start = None
        xs, ys = selection.overlay(points)
        self.selected_points = len(xs)
        if len(xs):
            style = implot.Spec()
            style.marker_size = 3
            style.marker = implot.Marker_.square
            style.line_weight = 0
            style.marker_fill_color = imgui.ImVec4(1, 0.7, 0.2, 1)
            style.marker_line_color = imgui.ImVec4(1, 0.7, 0.2, 1)
            implot.plot_scatter("Selected source rows", xs, ys, style)
