"""Standalone distribution charts compose the same series used by pair diagonals."""

from abc import ABC, abstractmethod
from collections.abc import Callable

from imgui_bundle import implot

from datelier.gui.components.base import FrameContext
from datelier.gui.components.viewport import ViewportContent
from datelier.gui.profiles.series import (
    BoxSeries,
    CumulativeSeries,
    DensitySeries,
    DistributionSeries,
    HistogramSeries,
    ViolinSeries,
)
from datelier.plotting.distributions import Comparison


class DistributionChart(ViewportContent, ABC):
    def __init__(self, prepared: Callable[[], Comparison | None]) -> None:
        self.series = self.make_series(prepared)
        super().__init__(self.series.label)
        self.prepared = prepared
        self.children = (self.series,)

    @abstractmethod
    def make_series(
        self, prepared: Callable[[], Comparison | None]
    ) -> DistributionSeries: ...

    def render(self, frame: FrameContext) -> None:
        data = self.prepared()
        if data is None or not data.series:
            return
        if self.fit:
            implot.set_next_axes_to_fit()
        if implot.begin_plot("##distribution", (-1, self.height)):
            implot.setup_axes(
                "Column" if self.series.boxes else "Value",
                "Rows"
                if self.series.label == "Histogram" and not data.settings.density
                else self.series.ylabel,
            )
            if self.series.boxes:
                implot.setup_axis_ticks(
                    implot.ImAxis_.x1,
                    [float(i) for i in range(len(data.series))],
                    [s.name for s in data.series],
                )
            super().render(frame)
            implot.end_plot()
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
