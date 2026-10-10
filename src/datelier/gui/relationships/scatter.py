"""Scatter content owns drawing and linked-input children, with narrow commands."""

from collections.abc import Callable

import numpy as np
from imgui_bundle import imgui, implot

from datelier.gui.components.base import Component, FrameContext
from datelier.gui.components.native import help_tip
from datelier.gui.components.viewport import ViewportContent
from datelier.gui.relationships.primitives import draw_color_items, legend_hovered
from datelier.plotting.data import Scatter
from datelier.plotting.projection import projected_nearest
from datelier.plotting.selection import LinkedSelection


class ScatterInput(Component):
    def __init__(
        self,
        prepared: Callable[[], Scatter | None],
        selection: LinkedSelection,
        jump: Callable[[int], None],
    ) -> None:
        super().__init__("input")
        self.prepared, self.selection, self.jump = prepared, selection, jump
        self.visible: np.ndarray | None = None
        self.brush: tuple[float, float] | None = None

    def render(self, frame: FrameContext) -> None:
        points = self.prepared()
        if points is None:
            return
        implot.get_input_map().pan = imgui.MouseButton_.middle
        pos, size = implot.get_plot_pos(), implot.get_plot_size()
        mouse = implot.get_plot_mouse_pos()
        if implot.is_plot_hovered() and not legend_hovered():
            if imgui.is_mouse_clicked(imgui.MouseButton_.left):
                if imgui.get_io().key_shift:
                    self.brush = (mouse.x, mouse.y)
                else:
                    pixels = np.array(
                        [
                            (p.x, p.y)
                            for p in (
                                implot.plot_to_pixels(float(x), float(y))
                                for x, y in zip(points.x, points.y, strict=True)
                            )
                        ]
                    ).reshape(-1, 2)
                    inside = (
                        (pixels[:, 0] >= pos.x)
                        & (pixels[:, 0] <= pos.x + size.x)
                        & (pixels[:, 1] >= pos.y)
                        & (pixels[:, 1] <= pos.y + size.y)
                    )
                    if self.visible is not None:
                        inside &= self.visible
                    pixels[~inside] = np.nan
                    screen = imgui.get_io().mouse_pos
                    index = projected_nearest(
                        pixels, np.zeros(len(pixels)), (screen.x, screen.y)
                    )
                    if index is not None:
                        if self.selection.choose(
                            points.revision,
                            (int(points.row_ids[index]),),
                            toggle=imgui.get_io().key_ctrl,
                        ):
                            self.jump(int(points.positions[index]))
        if self.brush is not None:
            a, b = (
                implot.plot_to_pixels(*self.brush),
                implot.plot_to_pixels(mouse.x, mouse.y),
            )
            implot.push_plot_clip_rect()
            implot.get_plot_draw_list().add_rect(
                (min(a.x, b.x), min(a.y, b.y)),
                (max(a.x, b.x), max(a.y, b.y)),
                0xFF33AAFF,
            )
            implot.pop_plot_clip_rect()
            if imgui.is_mouse_released(imgui.MouseButton_.left):
                self.selection.rectangle(
                    points, *self.brush, mouse.x, mouse.y, visible=self.visible
                )
                self.brush = None
        selected = np.isin(points.row_ids, tuple(self.selection.row_ids))
        if self.visible is not None:
            selected &= self.visible
        if selected.any():
            implot.plot_scatter(
                "Selected rows",
                points.x[selected],
                points.y[selected],
                implot.Spec(
                    marker_fill_color=(1, 0.7, 0.2, 1),
                    marker_size=4,
                    flags=implot.ItemFlags_.no_legend,
                ),
            )


class ScatterPlot(ViewportContent):
    def __init__(
        self,
        prepared: Callable[[], Scatter | None],
        selection: LinkedSelection,
        jump: Callable[[int], None],
    ) -> None:
        super().__init__("scatter")
        self.prepared, self.selection = prepared, selection
        self.input = ScatterInput(prepared, selection, jump)
        self.children = (self.input,)
        self._points: Scatter | None = None

    def render(self, frame: FrameContext) -> None:
        points = self.prepared()
        if points is None:
            imgui.text("Choose at least two numeric columns.")
            return
        if points is not self._points:
            self.fit = True
            self._points = points
            self.input.brush = None
        imgui.text_wrapped(
            f"{len(points.x):,} displayed of {points.eligible_rows:,} eligible · "
            f"{points.total_rows - points.eligible_rows:,} excluded · "
            f"{len(self.selection.row_ids):,} selected"
        )
        if points.colors and points.colors.note:
            imgui.text_wrapped(points.colors.note)
        if self.fit:
            implot.set_next_axes_to_fit()
        if implot.begin_plot("##scatter", (-1, max(120, self.height - 45))):
            implot.setup_axes(points.x_name, points.y_name)
            chosen = np.isin(points.row_ids, tuple(self.selection.row_ids))
            self.input.visible = draw_color_items(points, chosen)
            super().render(frame)
            implot.end_plot()
            self.fit = False
        help_tip(
            "Wheel zooms; middle drag pans; double click fits. Click selects, "
            "Ctrl-click toggles and Shift-drag brushes visible points."
        )
