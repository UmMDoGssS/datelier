"""Bounded pair-grid containers own their cells and source-scoped input children."""

from collections.abc import Callable

import numpy as np
from imgui_bundle import imgui, implot

from datelier.gui.components.base import Container, FrameContext
from datelier.gui.components.native import help_tip, label_text, target
from datelier.gui.components.viewport import ViewportContent
from datelier.gui.relationships.diagonals import DiagonalContent
from datelier.gui.relationships.scatter import ScatterInput
from datelier.plotting.data import Scatter
from datelier.plotting.relationships import Relationships
from datelier.plotting.selection import LinkedSelection


class PairCell(Container):
    def __init__(
        self,
        prepared: Callable[[], Relationships | None],
        row: int,
        column: int,
        selection: LinkedSelection,
        jump: Callable[[int], None],
        choose: Callable[[str, str | None], None],
    ) -> None:
        super().__init__(f"{row}-{column}", ())
        self.prepared, self.row, self.column, self.choose, self.selection = (
            prepared,
            row,
            column,
            choose,
            selection,
        )
        self.diagonal = DiagonalContent(prepared, row)
        self.input = ScatterInput(self.points, selection, jump)
        self.fit = True
        self._points: Scatter | None = None

    def points(self) -> Scatter | None:
        data = self.prepared()
        return data.cells[self.row][self.column] if data else None

    def render(self, frame: FrameContext) -> None:
        data = self.prepared()
        if data is None:
            return
        x, y = data.names[self.column], data.names[self.row]
        diagonal = self.row == self.column
        dense = len(data.names) > 4
        if self.fit:
            implot.set_next_axes_to_fit()
        title = label_text(f"{y} / {x}") + f"##{self.key}"
        flags = implot.Flags_.no_legend | (implot.Flags_.no_title if dense else 0)
        if not implot.begin_plot(title, flags=flags):
            return
        xlabel, ylabel = (
            self.diagonal.axes(x, data.diagonal_mode) if diagonal else (x, y)
        )
        implot.setup_axes(
            x if dense and self.row == 0 else "" if dense else xlabel,
            y if dense and self.column == 0 else "" if dense else ylabel,
            implot.AxisFlags_.no_tick_labels | implot.AxisFlags_.opposite
            if dense
            else 0,
            implot.AxisFlags_.no_tick_labels if dense else 0,
        )
        points = self.points()
        if diagonal:
            if data.diagonal_mode in (3, 4):
                implot.setup_axis_ticks(implot.ImAxis_.x1, [0.0], [x])
            self.children = (self.diagonal,)
        elif points:
            if points is not self._points:
                self._points = points
                self.input.brush = None
            mask = (
                np.isin(points.row_ids, tuple(self.selection.row_ids))
                if self.selection.revision == points.revision
                else np.zeros(len(points.x), dtype=bool)
            )
            implot.plot_scatter(
                "Rows",
                points.x[~mask],
                points.y[~mask],
                implot.Spec(marker=implot.Marker_.square, marker_size=1, line_weight=0),
            )
            self.input.visible = None
            self.children = (self.input,)
        else:
            self.children = ()
        super().render(frame)
        if implot.is_plot_hovered():
            imgui.set_tooltip(
                self.diagonal.details(data) if diagonal else f"X: {x} · Y: {y}"
            )
            if (
                imgui.is_mouse_double_clicked(imgui.MouseButton_.left)
                or diagonal
                and imgui.is_mouse_clicked(imgui.MouseButton_.left)
            ):
                self.choose(x, None if diagonal else y)
        implot.end_plot()
        target(frame, "plot")
        self.fit = False

    def close(self) -> None:
        self.children = ()
        self.diagonal.close()
        self.input.visible = None
        self.input.brush = None
        self._points = None


class PairGrid(ViewportContent):
    def __init__(
        self,
        prepared: Callable[[], Relationships | None],
        selection: LinkedSelection,
        jump: Callable[[int], None],
        choose: Callable[[str, str | None], None],
    ) -> None:
        super().__init__("pair-grid")
        self.prepared, self.selection, self.jump, self.choose = (
            prepared,
            selection,
            jump,
            choose,
        )
        self._names: tuple[str, ...] = ()
        self._stamp: tuple[object, ...] = ()
        self._native_id = 0
        self.cells: tuple[PairCell, ...] = ()

    def render(self, frame: FrameContext) -> None:
        data = self.prepared()
        if data is None or not data.names:
            imgui.text_wrapped("Choose numeric features to compare.")
            return
        n = len(data.names)
        if n > 8:
            imgui.text_wrapped(
                "Pair grids support up to eight features. The heatmap supports sixteen."
            )
            return
        if data.names != self._names:
            for cell in self.cells:
                cell.close()
            self._names = data.names
            self.cells = tuple(
                PairCell(self.prepared, i, j, self.selection, self.jump, self.choose)
                for i in range(n)
                for j in range(n)
            )
        stamp = data.names, data.diagonal_mode, id(data)
        if stamp != self._stamp:
            self._stamp, self.fit = stamp, True
        imgui.text_wrapped(
            f"{n} features · {data.sampled_rows:,} / {data.total_rows:,} rows · "
            "up to 150 sampled points per cell. Diagonal histogram/box includes "
            "all finite values; KDE/ECDF/violin use up to 2,000 finite samples "
            "per feature."
        )
        label_width = max(imgui.calc_text_size(name).x for name in data.names)
        width = n * max(120, label_width + 40)
        height = max(n * max(100 if n > 4 else 160, label_width + 30), self.height - 20)
        imgui.set_next_window_content_size((width, height))
        if not self._native_id:
            self._native_id = imgui.get_id("grid-content")
        if imgui.begin_child(
            "grid",
            (-1, self.height),
            window_flags=imgui.WindowFlags_.horizontal_scrollbar,
        ):
            imgui.internal.push_override_id(self._native_id)
            if implot.begin_subplots("##pairs", n, n, (-1, height)):
                for cell in self.cells:
                    cell.fit = self.fit or cell.fit
                self.children = self.cells
                super().render(frame)
                implot.end_subplots()
                self.fit = False
            imgui.pop_id()
        imgui.end_child()
        help_tip(
            "Click a point to select its original row. Double-click a pair "
            "to open its axes; click a diagonal to open Profiles."
        )

    def close(self) -> None:
        self.children = ()
        for cell in self.cells:
            cell.close()
        self.cells = ()
        self._names = self._stamp = ()
