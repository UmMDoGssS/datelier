"""Original-unit common scalar bins and native per-source legends."""

from imgui_bundle import implot

from datelier.gui.plots.axes import AxisControls
from datelier.inspection.audio.comparisons.types import (
    AudioComparisonCurve,
    PreparedAudioComparison,
)


def draw_curve(
    result: PreparedAudioComparison,
    curve: AudioComparisonCurve,
    proportions: bool,
    height: float,
    fit: bool,
    axes: AxisControls,
) -> bool:
    if fit:
        implot.set_next_axes_to_fit()
    if not implot.begin_plot("##Common audio distribution", (-1, height)):
        return False
    x_label = (
        f"{curve.metric.label} (scaled 0–1)" if curve.scaled else curve.metric.label
    )
    implot.setup_axes(
        x_label, "Proportion of finite records" if proportions else "Record count"
    )
    axes.apply()
    paths = curve.proportions if proportions else curve.counts
    for index, path in enumerate(paths):
        if path is not None:
            implot.plot_stairs(
                f"{result.labels[index]}##AudioSource{index}",
                curve.plot_x,
                path,
                implot.Spec(flags=implot.StairsFlags_.pre_step),
            )
    axes.observe()
    implot.end_plot()
    return True
