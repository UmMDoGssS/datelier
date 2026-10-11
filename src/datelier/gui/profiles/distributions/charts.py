"""Standalone distribution charts compose the same series used by pair diagonals."""

from abc import ABC, abstractmethod
from collections.abc import Callable

from imgui_bundle import implot

from datelier.gui.components.layout import FrameContext
from datelier.gui.components.native import target
from datelier.gui.components.plots import AxisPlot, apply_axes, observe_axes
from datelier.gui.profiles.distributions.series import (
    BoxSeries,
    CumulativeSeries,
    DensitySeries,
    DistributionSeries,
    HistogramSeries,
    ViolinSeries,
)
from datelier.plotting.distributions import Comparison


class DistributionChart(AxisPlot, ABC):
    def __init__(self, prepared: Callable[[], Comparison | None]) -> None:
        self.series = self.make_series(prepared)
        super().__init__(self.series.label)
        self.prepared = prepared
        self.children = (self.series,)

    @abstractmethod
    def make_series(
        self, prepared: Callable[[], Comparison | None]
    ) -> DistributionSeries: ...

    def plot_scope(self) -> object:
        return id(self.prepared())

    def numeric_axes(self) -> tuple[bool, bool]:
        return not self.series.boxes, True

    def render_plot(self, frame: FrameContext) -> None:
        data = self.prepared()
        if data is None or not data.series:
            return
        if self.fit:
            implot.set_next_axes_to_fit()
        if implot.begin_plot("##distribution", (-1, max(120, self.height - 30))):
            implot.setup_axes(
                "Column"
                if self.series.boxes
                else "Z-score"
                if data.settings.standardize
                else "Value",
                "Z-score"
                if self.series.boxes and data.settings.standardize
                else "Rows"
                if self.series.label == "Histogram" and not data.settings.density
                else self.series.ylabel,
            )
            if self.series.boxes:
                implot.setup_axis_ticks(
                    implot.ImAxis_.x1,
                    [float(i) for i in range(len(data.series))],
                    [s.name for s in data.series],
                )
            apply_axes(self.axes)
            self.render_children(frame)
            observe_axes(self.axes, frame)
            implot.end_plot()
            target(frame, "canvas")
            self.fit = False


class HistogramChart(DistributionChart):
    def make_series(
        self, prepared: Callable[[], Comparison | None]
    ) -> DistributionSeries:
        return HistogramSeries(prepared)


class DensityChart(DistributionChart):
    def make_series(
        self, prepared: Callable[[], Comparison | None]
    ) -> DistributionSeries:
        return DensitySeries(prepared)


class CumulativeChart(DistributionChart):
    def make_series(
        self, prepared: Callable[[], Comparison | None]
    ) -> DistributionSeries:
        return CumulativeSeries(prepared)


class BoxChart(DistributionChart):
    def make_series(
        self, prepared: Callable[[], Comparison | None]
    ) -> DistributionSeries:
        return BoxSeries(prepared)


class ViolinChart(DistributionChart):
    def make_series(
        self, prepared: Callable[[], Comparison | None]
    ) -> DistributionSeries:
        return ViolinSeries(prepared)


CHARTS = (HistogramChart, DensityChart, CumulativeChart, BoxChart, ViolinChart)
