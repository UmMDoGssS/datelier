"""Polymorphic distribution renderers over worker-prepared arrays."""

from abc import ABC, abstractmethod
from collections.abc import Callable

import numpy as np
from imgui_bundle import implot

from datelier.gui.components.base import FrameContext
from datelier.gui.components.viewport import ViewportContent
from datelier.gui.profiles.colors import profile_color
from datelier.gui.profiles.primitives import draw_box
from datelier.plotting.distributions import Comparison, NumericDistribution


class DistributionChart(ViewportContent, ABC):
    label = "Distribution"
    boxes = False
    ylabel = "Density"

    def __init__(self, prepared: Callable[[], Comparison | None]) -> None:
        super().__init__(self.label)
        self.prepared = prepared

    def render(self, frame: FrameContext) -> None:
        data = self.prepared()
        if data is None or not data.series:
            return
        if self.fit:
            implot.set_next_axes_to_fit()
        if implot.begin_plot("##distribution", (-1, self.height)):
            implot.setup_axes("Column" if self.boxes else "Value", self.ylabel)
            if self.boxes:
                implot.setup_axis_ticks(
                    implot.ImAxis_.x1,
                    [float(i) for i in range(len(data.series))],
                    [s.name for s in data.series],
                )
            for index, series in enumerate(data.series):
                self.draw(data, series, index)
            implot.end_plot()
            self.fit = False

    @abstractmethod
    def draw(
        self, data: Comparison, series: NumericDistribution, index: int
    ) -> None: ...


class HistogramChart(DistributionChart):
    label = "Histogram"

    def draw(self, data: Comparison, series: NumericDistribution, index: int) -> None:
        if not len(series.histogram):
            return
        color = profile_color(series.name)
        implot.plot_stairs(
            series.name,
            np.concatenate(([data.edges[0]], data.edges, [data.edges[-1]])),
            np.concatenate(([0, series.histogram[0]], series.histogram, [0])),
            implot.Spec(
                line_color=color,
                fill_color=color,
                fill_alpha=0.2,
                flags=implot.StairsFlags_.pre_step | implot.StairsFlags_.shaded,
            ),
        )


class DensityChart(DistributionChart):
    label = "KDE"

    def draw(self, data: Comparison, series: NumericDistribution, index: int) -> None:
        if len(series.kde_y):
            implot.plot_line(
                series.name,
                series.kde_x,
                series.kde_y,
                implot.Spec(line_color=profile_color(series.name)),
            )


class CumulativeChart(DistributionChart):
    label = "ECDF"
    ylabel = "Cumulative probability"

    def draw(self, data: Comparison, series: NumericDistribution, index: int) -> None:
        if len(series.ecdf_x):
            implot.plot_stairs(
                series.name,
                np.concatenate(([series.ecdf_x[0]], series.ecdf_x)),
                np.concatenate(([0.0], series.ecdf_y)),
                implot.Spec(line_color=profile_color(series.name)),
            )


class BoxChart(DistributionChart):
    label = "Box"
    boxes = True
    ylabel = "Value"

    def draw(self, data: Comparison, series: NumericDistribution, index: int) -> None:
        draw_box(series, index, False, profile_color(series.name))


class ViolinChart(BoxChart):
    label = "Violin"

    def draw(self, data: Comparison, series: NumericDistribution, index: int) -> None:
        draw_box(series, index, True, profile_color(series.name))


CHARTS = (HistogramChart, DensityChart, CumulativeChart, BoxChart, ViolinChart)
