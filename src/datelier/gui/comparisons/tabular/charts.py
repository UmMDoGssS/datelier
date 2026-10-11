"""Numeric and categorical comparison charts share legends and row-link input."""

from abc import ABC, abstractmethod

import numpy as np
from imgui_bundle import imgui, implot

from datelier.application.comparisons.columns import (
    ColumnComparisonController,
    ColumnSeries,
)
from datelier.core.column_roles import ColumnRole
from datelier.gui.components.layout import FrameContext
from datelier.gui.components.layout.viewport import ViewportContent
from datelier.gui.components.native import label_text, target
from datelier.gui.components.plots import AxisPlot, apply_axes, observe_axes
from datelier.gui.profiles.distributions import profile_color
from datelier.inspection.comparison_settings import Normalization
from datelier.inspection.comparisons.types import PreparedComparison


class ColumnComparisonPlot(AxisPlot, ABC):
    def __init__(self, model: ColumnComparisonController) -> None:
        super().__init__("column-chart")
        self.model = model
        self._prepared: PreparedComparison | None = None

    @abstractmethod
    def setup_axes(self, result: PreparedComparison) -> None: ...

    @abstractmethod
    def draw(
        self, series: ColumnSeries, label: str, style: implot.Spec, width: float
    ) -> None: ...

    @abstractmethod
    def bin_index(self, result: PreparedComparison, mouse: implot.Point) -> int: ...

    def plot_scope(self) -> object:
        return id(self.model.active)

    def render_plot(self, frame: FrameContext) -> None:
        result = self.model.active
        if result is None:
            return
        if result is not self._prepared:
            self._prepared, self.fit = result, True
        if self.fit:
            implot.set_next_axes_to_fit()
        if implot.begin_plot("##comparison", (-1, max(120, self.height - 30))):
            self.setup_axes(result)
            apply_axes(self.axes)
            implot.setup_legend(
                implot.Location_.north,
                implot.LegendFlags_.outside | implot.LegendFlags_.horizontal,
            )
            labels = []
            for series in self.model.series:
                label = label_text(series.label) + f"##{series.identity}"
                labels.append(label)
                color = (
                    imgui.ImVec4(*series.color)
                    if series.color
                    else profile_color(series.identity)
                )
                self.draw(
                    series,
                    label,
                    implot.Spec(line_color=color, fill_color=color, fill_alpha=0.25),
                    0.8 / len(result.series),
                )
            source = self.model.selected_source
            if (
                implot.is_plot_hovered()
                and labels
                and implot.internal.get_item(labels[source]).show
            ):
                index = self.bin_index(result, implot.get_plot_mouse_pos())
                chosen = result.series[source]
                counts = chosen.counts
                if 0 <= index < len(counts):
                    imgui.set_tooltip(
                        f"{chosen.label}: {counts[index]:,} source rows\n"
                        "Click to select rows in this source."
                    )
                    if imgui.is_mouse_clicked(imgui.MouseButton_.left):
                        self.model.select(source, index)
            implot.get_input_map().pan = imgui.MouseButton_.middle
            observe_axes(self.axes, frame)
            implot.end_plot()
            target(frame, "canvas")
            self.fit = False

    def close(self) -> None:
        self._prepared = None
        super().close()


class NumericComparisonPlot(ColumnComparisonPlot):
    def setup_axes(self, result: PreparedComparison) -> None:
        label = "Value" + (f" / {result.scale:.6g}" if result.scale != 1 else "")
        implot.setup_axes(
            label,
            "Density"
            if result.settings.normalization == Normalization.DENSITY
            else "Rows",
        )

    def draw(
        self, series: ColumnSeries, label: str, style: implot.Spec, width: float
    ) -> None:
        implot.plot_shaded(label, series.x, series.y, spec=style)
        implot.hide_next_item(
            not implot.internal.get_item(label).show, implot.Cond_.always
        )
        implot.plot_line(
            "Outline##" + series.identity,
            series.x,
            series.y,
            implot.Spec(line_color=style.line_color, flags=implot.ItemFlags_.no_legend),
        )

    def bin_index(self, result: PreparedComparison, mouse: implot.Point) -> int:
        return (
            0
            if mouse.x == result.edges[0]
            else int(np.searchsorted(result.edges, mouse.x, side="left") - 1)
        )


class CategoryComparisonPlot(ColumnComparisonPlot):
    def numeric_axes(self) -> tuple[bool, bool]:
        return True, False

    def setup_axes(self, result: PreparedComparison) -> None:
        implot.setup_axes(
            "Proportion"
            if result.settings.normalization == Normalization.DENSITY
            else "Rows",
            "Category",
        )
        implot.setup_axis_ticks(
            implot.ImAxis_.y1,
            [float(i) for i in range(len(result.labels))],
            list(result.labels),
        )

    def draw(
        self, series: ColumnSeries, label: str, style: implot.Spec, width: float
    ) -> None:
        style.flags = implot.BarsFlags_.horizontal
        style.fill_alpha = 0.85
        implot.plot_bars(label, series.x, series.y, width, style)

    def bin_index(self, result: PreparedComparison, mouse: implot.Point) -> int:
        return int(np.floor(mouse.y + 0.5))


class ColumnChart(ViewportContent):
    def __init__(self, model: ColumnComparisonController) -> None:
        super().__init__("column-chart")
        self.model = model
        self.routes = {
            ColumnRole.NUMERIC: NumericComparisonPlot(model),
            ColumnRole.CATEGORY: CategoryComparisonPlot(model),
        }

    def render(self, frame: FrameContext) -> None:
        result = self.model.active
        child = self.routes.get(result.kind) if result else None
        if child:
            child.height, child.fit = self.height, self.fit or child.fit
            self.children = (child,)
            super().render(frame)
            self.fit = child.fit

    def close(self) -> None:
        self.children = ()
        for child in self.routes.values():
            child.close()
