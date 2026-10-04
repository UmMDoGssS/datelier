"""Heatmap and bounded subplot grid with navigation and linked selection."""

import math
from dataclasses import dataclass, field

import numpy as np
from imgui_bundle import imgui, implot

from datelier.gui_selection import ScatterInteraction
from datelier.gui_table import TableView
from datelier.relationships import Relationships
from datelier.selection import LinkedSelection


@dataclass
class RelationshipView:
    mode: int = 0
    frames: int = 0
    pair_pixel: tuple[float, float] = (0, 0)
    interactions: dict[tuple[int, int], ScatterInteraction] = field(
        default_factory=dict
    )

    def show(
        self, data: Relationships, selection: LinkedSelection, table: TableView
    ) -> tuple[str, str | None] | None:
        _, self.mode = imgui.combo(
            "Relationship view", self.mode, ["Heatmap", "Distribution / scatter grid"]
        )
        imgui.text_wrapped(
            f"Pearson: {data.sampled_rows:,} of {data.total_rows:,} input rows; "
            "pairwise finite values. Gray = undefined. Click a cell to open its "
            "profile/scatter; grid clicks select points, double-click opens axes."
        )
        if not data.names:
            imgui.text("Choose numeric relationship features in Plot settings.")
            return None
        return (
            self._heatmap(data)
            if self.mode == 0
            else self._grid(data, selection, table)
        )

    def _heatmap(self, data: Relationships) -> tuple[str, str | None] | None:
        n = len(data.names)
        action = None
        if implot.begin_plot("Pearson heatmap", (-1, 280), implot.Flags_.no_legend):
            implot.setup_axes("Feature X", "Feature Y")
            implot.setup_axes_limits(0, n, 0, n, imgui.Cond_.always)
            ticks = [i + 0.5 for i in range(n)]
            implot.setup_axis_ticks(implot.ImAxis_.x1, ticks, list(data.names))
            implot.setup_axis_ticks(implot.ImAxis_.y1, ticks, list(data.names))
            implot.push_colormap(implot.Colormap_.rd_bu)
            implot.plot_heatmap(
                "Pearson",
                np.nan_to_num(data.values[::-1]).copy(),
                -1,
                1,
                "",
                implot.Point(0, 0),
                implot.Point(n, n),
            )
            implot.pop_colormap()
            implot.push_plot_clip_rect()
            for i, j in zip(*np.nonzero(~np.isfinite(data.values)), strict=True):
                a, b = (
                    implot.plot_to_pixels(float(j), float(i)),
                    implot.plot_to_pixels(float(j + 1), float(i + 1)),
                )
                implot.get_plot_draw_list().add_rect_filled(
                    imgui.ImVec2(min(a.x, b.x), min(a.y, b.y)),
                    imgui.ImVec2(max(a.x, b.x), max(a.y, b.y)),
                    0xFF777777,
                )
            implot.pop_plot_clip_rect()
            pixel = implot.plot_to_pixels(min(1.5, n - 0.5), 0.5)
            self.pair_pixel = (pixel.x, pixel.y)
            if implot.is_plot_hovered():
                mouse = implot.get_plot_mouse_pos()
                i, j = math.floor(mouse.y), math.floor(mouse.x)
                if 0 <= i < n and 0 <= j < n:
                    value = data.values[i, j]
                    imgui.set_tooltip(
                        f"{data.names[j]} / {data.names[i]}: "
                        + (f"{value:.4f}" if np.isfinite(value) else "undefined")
                        + f" · {data.finite_counts[i, j]:,} finite pairs"
                    )
                    if imgui.is_mouse_clicked(imgui.MouseButton_.left):
                        action = (data.names[j], data.names[i] if i != j else None)
            implot.end_plot()
            self.frames += 1
        imgui.text("Scale: −1 (red) · 0 (white) · +1 (blue)")
        return action

    def _grid(
        self, data: Relationships, selection: LinkedSelection, table: TableView
    ) -> tuple[str, str | None] | None:
        n = len(data.names)
        if n > 8:
            imgui.text_wrapped(
                "Select at most eight relationship features for the grid."
            )
            return None
        action = None
        imgui.text_wrapped(
            "At most 150 sampled points per cell. Diagonal histograms use "
            "bin indices; open the profile for bin boundaries."
        )
        if implot.begin_subplots("Pair grid", n, n, (-1, max(280, n * 120))):
            for i, y in enumerate(data.names):
                for j, x in enumerate(data.names):
                    if not implot.begin_plot(
                        f"{y} / {x}##{i}-{j}", flags=implot.Flags_.no_legend
                    ):
                        continue
                    implot.setup_axes(
                        x if i != j else "Bin",
                        y if i != j else "Rows",
                        implot.AxisFlags_.auto_fit,
                        implot.AxisFlags_.auto_fit,
                    )
                    points = data.cells[i][j]
                    if points is None:
                        bars = data.diagonals[i]
                        if len(bars.counts):
                            implot.plot_bars(x, bars.positions, bars.counts, 0.8)
                    else:
                        style = implot.Spec()
                        style.marker_size = 1
                        xs, ys = selection.unselected(points)
                        implot.plot_scatter("Rows", xs, ys, style)
                        interaction = self.interactions.setdefault(
                            (i, j), ScatterInteraction()
                        )
                        interaction.show(points, selection, table)
                    if implot.is_plot_hovered() and (
                        imgui.is_mouse_double_clicked(imgui.MouseButton_.left)
                        or i == j
                        and imgui.is_mouse_clicked(imgui.MouseButton_.left)
                    ):
                        action = (x, y if i != j else None)
                    implot.end_plot()
            implot.end_subplots()
            self.frames += 1
        return action
