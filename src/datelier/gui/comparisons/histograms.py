"""One scalar histogram component for compatible image and audio comparisons."""

from collections.abc import Callable

from imgui_bundle import imgui, implot

from datelier.application.comparisons.histograms import HistogramPlot
from datelier.gui.components.base import FrameContext
from datelier.gui.components.native import target
from datelier.gui.components.viewport import ViewportContent
from datelier.gui.profiles.colors import profile_color


class ComparisonHistogram(ViewportContent):
    def __init__(
        self,
        key: str,
        read: Callable[[], HistogramPlot | None],
        select: Callable[[float], None],
    ) -> None:
        super().__init__(key)
        self.read, self.select = read, select
        self._stamp: tuple[object, ...] = ()

    def render(self, frame: FrameContext) -> None:
        plot = self.read()
        if plot is None or not plot.series:
            imgui.text_wrapped(
                "No compatible ready values. Inspect the record outcomes."
            )
            return
        if plot.stamp != self._stamp:
            self._stamp, self.fit = plot.stamp, True
        if plot.note:
            imgui.text_wrapped(plot.note)
        if self.fit:
            implot.set_next_axes_to_fit()
        if implot.begin_plot("##histogram", (-1, self.height)):
            implot.setup_axes(plot.xlabel, plot.ylabel)
            implot.setup_legend(
                implot.Location_.north,
                implot.LegendFlags_.outside | implot.LegendFlags_.horizontal,
            )
            selected_visible = False
            for series in plot.series:
                color = profile_color(series.identity)
                label = series.label.replace("##", "#\u200b#") + "##" + series.identity
                implot.plot_stairs(
                    label,
                    series.x,
                    series.y,
                    implot.Spec(
                        line_color=color,
                        fill_color=color,
                        fill_alpha=0.18,
                        flags=implot.StairsFlags_.pre_step | implot.StairsFlags_.shaded,
                    ),
                )
                if series.identity == plot.selected:
                    selected_visible = implot.internal.get_item(label).show
            if (
                selected_visible
                and implot.is_plot_hovered()
                and imgui.is_mouse_clicked(imgui.MouseButton_.left)
            ):
                self.select(implot.get_plot_mouse_pos().x)
            implot.get_input_map().pan = imgui.MouseButton_.middle
            implot.end_plot()
            target(frame, "canvas")
            self.fit = False

    def close(self) -> None:
        self._stamp = ()
        super().close()
