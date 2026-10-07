"""Render worker-prepared dimension and channel histograms with native legends."""

from imgui_bundle import imgui, implot

from datelier.gui.plots.axes import AxisControls
from datelier.inspection.images.profile_types import ImageHistogram

CHANNEL_COLORS = {
    "R": (0.9, 0.28, 0.25, 1),
    "G": (0.25, 0.8, 0.35, 1),
    "B": (0.3, 0.55, 0.95, 1),
    "A": (0.75, 0.75, 0.75, 1),
    "C": (0.25, 0.8, 0.9, 1),
    "M": (0.85, 0.3, 0.8, 1),
    "Y": (0.9, 0.8, 0.2, 1),
    "K": (0.65, 0.65, 0.65, 1),
}


def draw_histograms(
    charts: tuple[ImageHistogram, ...],
    names: tuple[str, ...],
    label: str,
    ylabel: str,
    height: float,
    fit: bool,
    axes: AxisControls,
    normalized: bool = False,
) -> bool:
    if fit:
        implot.set_next_axes_to_fit()
    if not implot.begin_plot("##Image distribution", (-1, height)):
        return False
    implot.setup_axes(label, ylabel)
    axes.apply()
    for chart, name in zip(charts, names, strict=True):
        x = chart.normalized_plot_x if normalized else chart.plot_x
        if x is None or chart.plot_counts is None:
            continue
        color = imgui.ImVec4(*CHANNEL_COLORS.get(name, (0.4, 0.7, 0.9, 1)))
        style = implot.Spec(
            line_color=color, fill_color=imgui.ImVec4(color.x, color.y, color.z, 0.18)
        )
        style.flags = implot.StairsFlags_.pre_step | implot.StairsFlags_.shaded
        implot.plot_stairs(name, x, chart.plot_counts, style)
    axes.observe()
    implot.end_plot()
    return True
