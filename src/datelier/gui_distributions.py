"""Prepared comparison rendering, with selectable ImPlot series legends."""

import numpy as np
from imgui_bundle import imgui, implot

from datelier.distributions import Comparison, NumericDistribution
from datelier.gui_axes import AxisControls

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


def show_comparison(
    comparison: Comparison,
    mode: int,
    fit: bool,
    *,
    title: str = "Column comparison",
    details: bool = True,
    height: float = 220,
    axes: AxisControls | None = None,
) -> bool:
    start_y = imgui.get_cursor_screen_pos().y
    settings = comparison.settings
    if not comparison.series:
        imgui.text_wrapped("Select numeric comparison columns in Plot settings.")
        return False
    if details:
        imgui.text(f"{'Z-score' if settings.standardize else 'Original'} units")
    for series in comparison.series:
        if mode in (1, 2, 4) and series.sample_count < series.count:
            imgui.text(
                f"{series.name}: {series.sample_count:,} sampled / "
                f"{series.count:,} included"
            )
    if details and imgui.collapsing_header("Counts and sample details"):
        imgui.text_wrapped(
            f"Seed {settings.seed} · KDE bandwidth {settings.bandwidth:g}. "
            "KDE/ECDF/violin use at most 2,000 finite values per column. "
            "Histogram and box statistics use all finite values; displayed "
            "outliers use the sample, capped at 150 per column."
        )
        for series in comparison.series:
            imgui.text_wrapped(
                f"{series.name}: {series.count:,} finite, "
                f"{series.sample_count:,} sampled. " + series.note
            )
    if mode in (1, 4):
        for series in comparison.series:
            if not len(series.kde_y):
                imgui.text_wrapped(
                    f"{series.name}: density unavailable for these values. "
                    "Try Histogram or ECDF."
                )
        if not any(len(series.kde_y) for series in comparison.series):
            return False
    if fit:
        implot.set_next_axes_to_fit()
    height = max(170, height - (imgui.get_cursor_screen_pos().y - start_y))
    horizontal_boxes = mode in (3, 4)
    implot.push_style_var(
        implot.StyleVar_.fit_padding,
        imgui.ImVec2(0.08, 0.05 if horizontal_boxes else 0),
    )
    flags = implot.Flags_.no_legend if len(comparison.series) == 1 else 0
    if not implot.begin_plot(title, (-1, height), flags):
        implot.pop_style_var()
        return False
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
    if axes is not None:
        axes.apply()
    for i, series in enumerate(comparison.series):
        if mode == 0:
            hist_style = implot.Spec()
            hist_style.flags = implot.StairsFlags_.pre_step
            implot.plot_stairs(
                series.name,
                comparison.edges,
                np.concatenate(([series.histogram[0]], series.histogram)),
                hist_style,
            )
        elif mode == 1 and len(series.kde_y):
            implot.plot_line(series.name, series.kde_x, series.kde_y)
        elif mode == 2 and len(series.ecdf_x):
            # Include the zero baseline at the first observation; ties have one
            # jump whose height includes every repeated observation.
            xs = np.concatenate(([series.ecdf_x[0]], series.ecdf_x))
            ys = np.concatenate(([0.0], series.ecdf_y))
            implot.plot_stairs(series.name, xs, ys)
        elif horizontal_boxes and (mode == 3 or len(series.kde_y)):
            _box(series, i, mode == 4)
    if axes is not None:
        axes.observe()
    implot.end_plot()
    implot.pop_style_var()
    return True
