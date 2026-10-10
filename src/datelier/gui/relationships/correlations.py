"""Correlation heatmap and pair-grid families over the same prepared matrix."""

from collections.abc import Callable
from math import floor

import numpy as np
from imgui_bundle import imgui, implot

from datelier.gui.components.base import FrameContext
from datelier.gui.components.viewport import ViewportContent
from datelier.plotting.relationships import Relationships


class CorrelationPlot(ViewportContent):
    def __init__(
        self,
        prepared: Callable[[], Relationships | None],
        choose_pair: Callable[[str, str | None], None],
    ) -> None:
        super().__init__("heatmap")
        self.prepared, self.choose_pair = prepared, choose_pair

    def render(self, frame: FrameContext) -> None:
        data = self.prepared()
        if data is None or not data.names:
            imgui.text("Choose numeric correlation features.")
            return
        n = len(data.names)
        imgui.text_wrapped(
            f"Pearson r · {data.sampled_rows:,} of {data.total_rows:,} rows · "
            "pairwise finite values; gray cells are undefined"
        )
        if implot.begin_plot(
            "##correlation", (-1, max(170, self.height - 35)), implot.Flags_.no_legend
        ):
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
            for i, j in np.argwhere(~np.isfinite(data.values)):
                a, b = (
                    implot.plot_to_pixels(float(j), float(i)),
                    implot.plot_to_pixels(float(j + 1), float(i + 1)),
                )
                implot.get_plot_draw_list().add_rect_filled(
                    (min(a.x, b.x), min(a.y, b.y)),
                    (max(a.x, b.x), max(a.y, b.y)),
                    0xFF777777,
                )
            implot.pop_plot_clip_rect()
            for i, j in np.argwhere(~np.isfinite(data.values)):
                implot.plot_text("—", float(j) + 0.5, float(i) + 0.5)
            if implot.is_plot_hovered():
                mouse = implot.get_plot_mouse_pos()
                i, j = floor(mouse.y), floor(mouse.x)
                if 0 <= i < n and 0 <= j < n:
                    imgui.set_tooltip(
                        f"{data.names[j]} / {data.names[i]}: "
                        f"{data.values[i, j]:.4g} · "
                        f"{data.finite_counts[i, j]:,} finite pairs"
                    )
                    if imgui.is_mouse_clicked(imgui.MouseButton_.left):
                        self.choose_pair(
                            data.names[j], data.names[i] if i != j else None
                        )
            implot.end_plot()
