"""Scatter content owns drawing and linked-input children, with narrow commands."""

from collections.abc import Callable

import numpy as np
from imgui_bundle import imgui, implot

from datelier.application.axes import AxisState
from datelier.gui.components.axes import AxisPlot, apply_axes, observe_axes
from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.components.native import help_tip, target
from datelier.gui.relationships.primitives import (
    draw_color_items,
    legend_hovered,
    with_color_scale,
)
from datelier.gui.relationships.summary import ScatterSummary
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
        if len(points.x):
            index = len(points.x) // 2
            point = implot.plot_to_pixels(
                float(points.x[index]), float(points.y[index])
            )
            frame.record("point", (point.x, point.y))
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
        selected = self.selection.mask(points)
        if self.visible is not None:
            selected = selected & self.visible
        frame.measure("selected", (float(selected.sum()), float(len(selected))))
        if selected.any():
            implot.plot_scatter(
                "Selected rows",
                points.x[selected],
                points.y[selected],
                implot.Spec(
                    marker_fill_color=(1, 0.7, 0.2, 1),
                    marker=implot.Marker_.square,
                    marker_size=3,
                    marker_line_color=(1, 0.7, 0.2, 1),
                    line_weight=0,
                    flags=implot.ItemFlags_.no_legend,
                ),
            )


class NativeScatter2D(Container):
    def __init__(
        self,
        prepared: Callable[[], Scatter | None],
        selection: LinkedSelection,
        jump: Callable[[int], None],
        axes: AxisState,
    ) -> None:
        self.input = ScatterInput(prepared, selection, jump)
        super().__init__("canvas", (self.input,))
        self.prepared, self.selection, self.axes = prepared, selection, axes
        self.height = 200.0
        self.fit = True

    def draw(self, width: float, frame: FrameContext) -> bool:
        points = self.prepared()
        if points is None:
            return False
        if self.fit:
            implot.set_next_axes_to_fit()
        if not implot.begin_plot("##scatter", (width, self.height)):
            return False
        implot.setup_axes(points.x_name, points.y_name)
        apply_axes(self.axes)
        chosen = self.selection.mask(points)
        self.input.visible = draw_color_items(points, chosen)
        super().render(frame)
        observe_axes(self.axes, frame)
        implot.end_plot()
        target(frame, "plot")
        self.fit = False
        return True

    def render(self, frame: FrameContext) -> None:
        points = self.prepared()
        if points:
            with_color_scale(points, self.height, lambda width: self.draw(width, frame))

    def close(self) -> None:
        self.input.visible = None
        self.input.brush = None
        super().close()


class ScatterPlot(AxisPlot):
    def __init__(
        self,
        prepared: Callable[[], Scatter | None],
        selection: LinkedSelection,
        jump: Callable[[int], None],
    ) -> None:
        super().__init__("scatter2d")
        self.prepared = prepared
        self._points: Scatter | None = None
        self.canvas = NativeScatter2D(prepared, selection, jump, self.axes)
        self.children = (ScatterSummary(prepared, selection), self.canvas)

    def plot_scope(self) -> object:
        return id(self.prepared())

    def render_plot(self, frame: FrameContext) -> None:
        points = self.prepared()
        if points is None:
            self.canvas.input.brush = None
            imgui.text_wrapped(
                "Choose two numeric columns or explicitly prepare "
                "the selected analysis source."
            )
            return
        if points is not self._points:
            self.fit = True
            self._points = points
            self.canvas.input.brush = None
        self.canvas.height, self.canvas.fit = (
            max(120, self.height - 85),
            self.fit or self.canvas.fit,
        )
        self.render_children(frame)
        self.fit = self.canvas.fit
        help_tip(
            "Wheel zooms; middle drag pans; double click fits. Click selects, "
            "Ctrl-click toggles and Shift-drag brushes visible points."
        )

    def close(self) -> None:
        self._points = None
        super().close()
