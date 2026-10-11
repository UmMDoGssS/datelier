"""Bounded array/tensor values with shared scalar/vector/matrix content families."""

import math
from abc import ABC, abstractmethod
from collections.abc import Callable

from imgui_bundle import imgui, implot

from datelier.application.sources.numeric import NumericSourceController
from datelier.gui.components.layout import Component, Container, FrameContext
from datelier.gui.components.layout.groups import Conditional
from datelier.gui.components.layout.viewport import ResizableViewport, ViewportContent
from datelier.gui.components.native import target
from datelier.gui.components.plots import (
    AxisPlot,
    apply_axes,
    native_colormap,
    observe_axes,
)
from datelier.inspection.arrays.slices import PreparedSlice


class SliceChart(AxisPlot, ABC):
    def __init__(self, key: str, prepared: Callable[[], PreparedSlice | None]) -> None:
        super().__init__(key)
        self.prepared = prepared

    def plot_scope(self) -> object:
        return id(self.prepared())

    @abstractmethod
    def render_plot(self, frame: FrameContext) -> None: ...


class VectorChart(SliceChart):
    def render_plot(self, frame: FrameContext) -> None:
        data = self.prepared()
        if data is None or data.numeric is None or not data.numeric.size:
            return
        if self.fit:
            implot.set_next_axes_to_fit()
        if implot.begin_plot("##vector", (-1, max(120, self.height - 30))):
            implot.setup_axes(f"Axis {data.axes[0]} index", "Value")
            apply_axes(self.axes)
            implot.plot_line("Values", data.numeric, xstart=float(data.starts[0]))
            observe_axes(self.axes, frame)
            implot.end_plot()
            target(frame, "canvas")
            self.fit = False


class MatrixChart(SliceChart):
    def render_plot(self, frame: FrameContext) -> None:
        data = self.prepared()
        if data is None or data.heatmap is None or not data.heatmap.size:
            return
        rows, columns = data.raw.shape
        if implot.begin_plot(
            "##matrix", (-1, max(120, self.height - 30)), implot.Flags_.no_legend
        ):
            row, column = data.starts
            implot.setup_axes(
                f"Axis {data.axes[1]} index", f"Axis {data.axes[0]} index"
            )
            implot.setup_axes_limits(
                column,
                column + columns,
                row,
                row + rows,
                imgui.Cond_.always if self.fit else imgui.Cond_.once,
            )
            apply_axes(self.axes)
            implot.push_colormap(native_colormap(data.settings.colormap))
            implot.plot_heatmap(
                "Display colors",
                data.heatmap,
                0,
                1,
                "",
                implot.Point(column, row),
                implot.Point(column + columns, row + rows),
            )
            implot.pop_colormap()
            implot.push_plot_clip_rect()
            for y, start, count in data.nonfinite_spans:
                a = implot.plot_to_pixels(float(column + start), float(row + y))
                b = implot.plot_to_pixels(
                    float(column + start + count), float(row + y + 1)
                )
                implot.get_plot_draw_list().add_rect_filled(
                    imgui.ImVec2(min(a.x, b.x), min(a.y, b.y)),
                    imgui.ImVec2(max(a.x, b.x), max(a.y, b.y)),
                    0xFFFF00FF,
                )
            implot.pop_plot_clip_rect()
            if implot.is_plot_hovered():
                mouse = implot.get_plot_mouse_pos()
                y, x = math.floor(mouse.y) - row, math.floor(mouse.x) - column
                if 0 <= y < rows and 0 <= x < columns:
                    coords = list(data.settings.fixed or (0,) * len(data.source_shape))
                    coords[data.axes[0]], coords[data.axes[1]] = row + y, column + x
                    imgui.set_tooltip(
                        f"Original index {tuple(coords)}: {data.cells[y][x]}"
                    )
            observe_axes(self.axes, frame)
            implot.end_plot()
            target(frame, "canvas")
            self.fit = False


class SlicePlots(ViewportContent):
    def __init__(self, prepared: Callable[[], PreparedSlice | None]) -> None:
        super().__init__("plot")
        self.prepared = prepared
        self.charts = {
            1: VectorChart("vector", prepared),
            2: MatrixChart("matrix", prepared),
        }

    def render(self, frame: FrameContext) -> None:
        data = self.prepared()
        child = (
            self.charts.get(len(data.axes))
            if data and data.numeric is not None
            else None
        )
        self.children = (child,) if child else ()
        if child:
            child.height, child.fit = self.height, self.fit
        super().render(frame)
        if child:
            self.fit = child.fit


class SliceCells(Component):
    def __init__(self, key: str, prepared: Callable[[], PreparedSlice | None]) -> None:
        super().__init__(key)
        self.prepared = prepared
        self.column_start = 0

    def render(self, frame: FrameContext) -> None:
        data = self.prepared()
        if data is None:
            return
        if data.diagnostic:
            imgui.text_wrapped(data.diagnostic)
        imgui.text_wrapped(
            f"Original shape {data.source_shape} · window {data.raw.shape} · "
            f"{data.raw.dtype} · axes {data.axes} · starts {data.starts}"
        )
        imgui.text_wrapped(
            f"Finite range {data.finite_range} · {data.nonfinite:,} nonfinite values · "
            f"{'bounded window' if data.limited else 'complete selected slice'}"
        )
        columns = len(data.cells[0]) if data.cells else 0
        if columns > 32:
            _, self.column_start = imgui.slider_int(
                "Column window", self.column_start, 0, max(0, columns - 32)
            )
        self.column_start = min(self.column_start, max(0, columns - 32))
        shown = min(32, columns - self.column_start)
        if columns and imgui.begin_table(
            "cells",
            shown + 1,
            imgui.TableFlags_.scroll_x
            | imgui.TableFlags_.scroll_y
            | imgui.TableFlags_.borders,
            (-1, 160),
        ):
            imgui.table_setup_column("Index")
            for i in range(self.column_start, self.column_start + shown):
                imgui.table_setup_column(
                    str((data.starts[-1] if len(data.axes) == 2 else 0) + i)
                )
            imgui.table_headers_row()
            clipper = imgui.ListClipper()
            clipper.begin(len(data.cells))
            while clipper.step():
                for index in range(clipper.display_start, clipper.display_end):
                    imgui.table_next_row()
                    imgui.table_next_column()
                    imgui.text(str((data.starts[0] if data.starts else 0) + index))
                    for value in data.cells[index][
                        self.column_start : self.column_start + shown
                    ]:
                        imgui.table_next_column()
                        imgui.text_unformatted(value)
            imgui.end_table()


class NumericContent(Container):
    def __init__(self, model: NumericSourceController) -> None:
        self.model = model
        super().__init__(
            "numeric-values",
            (
                Conditional(
                    "numeric",
                    lambda: bool(
                        model.prepared is not None
                        and model.prepared.axes
                        and model.prepared.numeric is not None
                    ),
                    (
                        ResizableViewport(
                            "array-plot",
                            SlicePlots(lambda: model.prepared),
                            read_height=lambda: model.height,
                            write_height=lambda value: setattr(model, "height", value),
                        ),
                    ),
                ),
                SliceCells("raw-values", lambda: model.prepared),
                SliceCells("storage-bits", lambda: model.storage),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        imgui.text_wrapped(self.model.jobs.message)
        prepared = self.model.prepared
        if prepared is not None:
            if prepared.settings != self.model.settings:
                imgui.text_wrapped(
                    "Showing the earlier slice. Prepare applies the current settings."
                )
            super().render(frame)
