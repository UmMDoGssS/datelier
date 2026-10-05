"""Annotated Pearson cells and a pinned color scale on a scrollable canvas."""

import math
from dataclasses import dataclass

import numpy as np
from imgui_bundle import imgui, implot

from datelier.gui.plots.axes import AxisControls
from datelier.plotting.relationships import Relationships


@dataclass
class HeatmapView:
    frames: int = 0
    pair_pixel: tuple[float, float] = (0, 0)

    def show(
        self, data: Relationships, height: float, axes: AxisControls
    ) -> tuple[str, str | None] | None:
        n = len(data.names)
        # Reserve readable cell values, the Y labels, and plot padding. Scroll
        # wide matrices while keeping their color key visible beside the canvas.
        label_width = max(imgui.calc_text_size(name).x for name in data.names)
        cell_width = max(46, label_width + 8, imgui.calc_text_size("−0.00").x + 12)
        minimum_width = label_width + n * cell_width + 55
        scale_width = 80.0
        canvas_width = max(80, imgui.get_content_region_avail().x - scale_width - 8)
        scroll = minimum_width > canvas_width
        plot_height = height - (imgui.get_style().scrollbar_size if scroll else 0)
        imgui.set_next_window_content_size((minimum_width if scroll else 0, 0))
        action = None
        shown = imgui.begin_child(
            "Heatmap canvas",
            (canvas_width, height),
            window_flags=imgui.WindowFlags_.horizontal_scrollbar,
        )
        if shown:
            action = self._plot(data, max(140, plot_height - 16), axes)
        imgui.end_child()
        imgui.same_line()
        implot.colormap_scale(
            "Pearson r",
            -1,
            1,
            (scale_width, height),
            "%.1f",
            cmap=implot.Colormap_.rd_bu,
        )
        return action

    def _plot(
        self, data: Relationships, height: float, axes: AxisControls
    ) -> tuple[str, str | None] | None:
        n = len(data.names)
        action = None
        if not implot.begin_plot(
            "Pearson heatmap", (-1, height), implot.Flags_.no_legend
        ):
            return None
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
            "%.2f",
            implot.Point(0, 0),
            implot.Point(n, n),
        )
        implot.pop_colormap()
        implot.push_plot_clip_rect()
        undefined = np.argwhere(~np.isfinite(data.values))
        for i, j in undefined:
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
        # The gray overlay covers the substituted numeric value. Draw a dash
        # afterward so undefined correlations never appear to be zero.
        implot.push_style_color(implot.Col_.inlay_text, (1, 1, 1, 1))
        for i, j in undefined:
            implot.plot_text("—", float(j) + 0.5, float(i) + 0.5)
        implot.pop_style_color()
        axes.observe()
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
        return action
