"""Distribution series components render inside a parent's native plot context."""

from abc import ABC, abstractmethod
from collections.abc import Callable

import numpy as np
from imgui_bundle import implot

from datelier.gui.components.layout import Component, FrameContext
from datelier.gui.components.native import label_text
from datelier.gui.profiles.distributions.colors import profile_color
from datelier.gui.profiles.distributions.primitives import draw_box
from datelier.plotting.distributions import Comparison, NumericDistribution


class DistributionSeries(Component, ABC):
    label = "Distribution"
    boxes = False
    ylabel = "Density"

    def __init__(self, prepared: Callable[[], Comparison | None]) -> None:
        super().__init__("series")
        self.prepared = prepared

    def render(self, frame: FrameContext) -> None:
        data = self.prepared()
        if data:
            for index, series in enumerate(data.series):
                self.draw(data, series, index)

    @abstractmethod
    def draw(
        self, data: Comparison, series: NumericDistribution, index: int
    ) -> None: ...


class HistogramSeries(DistributionSeries):
    label = "Histogram"

    def draw(self, data: Comparison, series: NumericDistribution, index: int) -> None:
        if not len(series.histogram):
            return
        color = profile_color(series.name)
        implot.plot_stairs(
            label_text(series.name),
            np.concatenate(([data.edges[0]], data.edges, [data.edges[-1]])),
            np.concatenate(([0, series.histogram[0]], series.histogram, [0])),
            implot.Spec(
                line_color=color,
                fill_color=color,
                fill_alpha=0.2,
                flags=implot.StairsFlags_.pre_step | implot.StairsFlags_.shaded,
            ),
        )


class DensitySeries(DistributionSeries):
    label = "KDE"

    def draw(self, data: Comparison, series: NumericDistribution, index: int) -> None:
        if len(series.kde_y):
            implot.plot_line(
                label_text(series.name),
                series.kde_x,
                series.kde_y,
                implot.Spec(line_color=profile_color(series.name)),
            )


class CumulativeSeries(DistributionSeries):
    label = "ECDF"
    ylabel = "Cumulative probability"

    def draw(self, data: Comparison, series: NumericDistribution, index: int) -> None:
        if len(series.ecdf_x):
            implot.plot_stairs(
                label_text(series.name),
                np.concatenate(([series.ecdf_x[0]], series.ecdf_x)),
                np.concatenate(([0.0], series.ecdf_y)),
                implot.Spec(line_color=profile_color(series.name)),
            )


class BoxSeries(DistributionSeries):
    label = "Box"
    boxes = True
    ylabel = "Value"

    def draw(self, data: Comparison, series: NumericDistribution, index: int) -> None:
        draw_box(series, index, False, profile_color(series.name))


class ViolinSeries(BoxSeries):
    label = "Violin"

    def draw(self, data: Comparison, series: NumericDistribution, index: int) -> None:
        draw_box(series, index, True, profile_color(series.name))


SERIES_TYPES = (
    HistogramSeries,
    DensitySeries,
    CumulativeSeries,
    BoxSeries,
    ViolinSeries,
)
