"""Shared plots over bounded worker-prepared physical histograms."""

from collections.abc import Callable

from imgui_bundle import imgui, implot

from datelier.gui.components.layout import FrameContext
from datelier.gui.components.layout.viewport import ViewportContent
from datelier.gui.profiles.distributions.colors import profile_color
from datelier.inspection.images.profiles import ImageHistogram


class HistogramContent(ViewportContent):
    def __init__(
        self,
        key: str,
        charts: Callable[[], tuple[ImageHistogram, ...]],
        xlabel: Callable[[], str],
        ylabel: str,
    ) -> None:
        super().__init__(key)
        self.charts, self.xlabel, self.ylabel = charts, xlabel, ylabel

    def render(self, frame: FrameContext) -> None:
        charts = self.charts()
        if not charts:
            imgui.text_wrapped(
                "No ready values. Inspect the record outcomes for diagnostics."
            )
            return
        normalized = any(chart.scaled for chart in charts)
        if normalized:
            imgui.text_wrapped(
                "Axis positions are scaled 0–1; "
                "exact original bounds remain in Statistics."
            )
        if self.fit:
            implot.set_next_axes_to_fit()
        if implot.begin_plot("##histogram", (-1, self.height)):
            implot.setup_axes(
                "Scaled " + self.xlabel() if normalized else self.xlabel(), self.ylabel
            )
            for chart in charts:
                x = chart.normalized_plot_x if normalized else chart.plot_x
                if x is None or chart.plot_counts is None:
                    continue
                color = profile_color(chart.label)
                implot.plot_stairs(
                    chart.label,
                    x,
                    chart.plot_counts,
                    implot.Spec(
                        line_color=color,
                        fill_color=color,
                        fill_alpha=0.18,
                        flags=implot.StairsFlags_.pre_step | implot.StairsFlags_.shaded,
                    ),
                )
            implot.end_plot()
            self.fit = False
