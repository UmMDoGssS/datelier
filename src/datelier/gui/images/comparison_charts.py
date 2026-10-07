"""Native legends over worker-prepared common physical count/proportion curves."""

from imgui_bundle import implot

from datelier.gui.plots.axes import AxisControls
from datelier.inspection.images.comparisons.types import (
    ImageComparisonCurve,
    PreparedImageComparison,
)


def draw_curve(
    result: PreparedImageComparison,
    curve: ImageComparisonCurve,
    proportions: bool,
    height: float,
    fit: bool,
    axes: AxisControls,
) -> bool:
    if fit:
        implot.set_next_axes_to_fit()
    if not implot.begin_plot("##Common image distribution", (-1, height)):
        return False
    chart = next((chart for chart in curve.counts if chart is not None), None)
    label = (
        f"{curve.key.name} (scaled 0–1)"
        if chart is not None and chart.scaled
        else curve.key.name
    )
    implot.setup_axes(label, "Proportion of finite values" if proportions else "Count")
    axes.apply()
    charts = curve.proportions if proportions else curve.counts
    for index, chart in enumerate(charts):
        if chart is None or chart.plot_x is None or chart.plot_counts is None:
            continue
        spec = implot.Spec(flags=implot.StairsFlags_.pre_step)
        implot.plot_stairs(
            f"{result.labels[index]}##Source{index}",
            chart.plot_x,
            chart.plot_counts,
            spec,
        )
    axes.observe()
    implot.end_plot()
    return True
