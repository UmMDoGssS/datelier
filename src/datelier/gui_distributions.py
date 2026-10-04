"""Prepared comparison rendering, with selectable ImPlot series legends."""

import numpy as np
from imgui_bundle import imgui, implot

from datelier.distributions import Comparison, NumericDistribution

MODES = ["Histogram", "KDE", "ECDF", "Box", "Violin"]


def _box(series: NumericDistribution, index: int, violin: bool) -> None:
    if series.box is None:
        return
    lo, q1, median, q3, hi = series.box
    center = float(index)
    if violin and len(series.kde_y):
        width = series.kde_y / series.kde_y.max() * 0.4
        xs = np.concatenate((center - width, (center + width)[::-1]))
        ys = np.concatenate((series.kde_x, series.kde_x[::-1]))
        implot.plot_line(series.name, xs, ys)
    else:
        xs = np.array(
            [
                center,
                center,
                np.nan,
                center - 0.3,
                center + 0.3,
                center + 0.3,
                center - 0.3,
                center - 0.3,
                np.nan,
                center - 0.3,
                center + 0.3,
            ]
        )
        ys = np.array([lo, hi, np.nan, q1, q1, q3, q3, q1, np.nan, median, median])
        implot.plot_line(series.name, xs, ys)
    if len(series.outliers):
        implot.plot_scatter(
            f"{series.name} outliers",
            np.full(len(series.outliers), center),
            series.outliers,
        )


def show_comparison(comparison: Comparison, mode: int, fit: bool) -> bool:
    settings = comparison.settings
    if not comparison.series:
        imgui.text_wrapped("Select numeric comparison columns in Plot settings.")
        return False
    imgui.text_wrapped(
        f"{'Z-score' if settings.standardize else 'Original'} units · seed "
        f"{settings.seed} · KDE/ECDF/violin sample at most 2,000 finite values "
        "per column. Histogram and box statistics use all finite values."
    )
    for series in comparison.series:
        imgui.text_wrapped(
            f"{series.name}: {series.count:,} finite, {series.sample_count:,} sampled. "
            + series.note
        )
    if fit:
        implot.set_next_axes_to_fit()
    if not implot.begin_plot("Column comparison", (-1, 220)):
        return False
    horizontal_boxes = mode in (3, 4)
    ylabel = (
        "Value"
        if horizontal_boxes
        else "Cumulative probability"
        if mode == 2
        else "Density"
        if mode == 1 or settings.density
        else "Rows"
    )
    implot.setup_axes("Column" if horizontal_boxes else "Value", ylabel)
    if horizontal_boxes:
        implot.setup_axis_ticks(
            implot.ImAxis_.x1,
            [float(i) for i in range(len(comparison.series))],
            [s.name for s in comparison.series],
        )
    centers = comparison.edges[:-1] + np.diff(comparison.edges) / 2
    for i, series in enumerate(comparison.series):
        if mode == 0:
            implot.plot_line(series.name, centers, series.histogram)
        elif mode == 1 and len(series.kde_y):
            implot.plot_line(series.name, series.kde_x, series.kde_y)
        elif mode == 2 and len(series.ecdf_x):
            # Include the zero baseline at the first observation; ties have one
            # jump whose height includes every repeated observation.
            xs = np.concatenate(([series.ecdf_x[0]], series.ecdf_x))
            ys = np.concatenate(([0.0], series.ecdf_y))
            implot.plot_stairs(series.name, xs, ys)
        elif horizontal_boxes:
            _box(series, i, mode == 4)
    implot.end_plot()
    return True
