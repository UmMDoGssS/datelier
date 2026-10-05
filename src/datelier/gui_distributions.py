"""Prepared comparison rendering, with selectable ImPlot series legends."""

import numpy as np
from imgui_bundle import imgui, implot

from datelier.distributions import Comparison, NumericDistribution
from datelier.gui_axes import AxisControls
from datelier.gui_profile_colors import profile_color

MODES = ["Histogram", "KDE", "ECDF", "Box", "Violin"]


def draw_box(
    series: NumericDistribution,
    index: int,
    violin: bool,
    color: imgui.ImVec4 | None = None,
) -> None:
    if series.box is None:
        return
    lo, q1, median, q3, hi = series.box
    center = float(index)
    if violin and len(series.kde_y):
        width = series.kde_y / series.kde_y.max() * 0.4
        xs = np.concatenate(
            (center - width, (center + width)[::-1], [center - width[0]])
        )
        ys = np.concatenate((series.kde_x, series.kde_x[::-1], series.kde_x[:1]))
        implot.plot_line(series.name, xs, ys, implot.Spec(line_color=color))
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
        implot.plot_line(series.name, xs, ys, implot.Spec(line_color=color))
    if len(series.outliers):
        implot.plot_scatter(
            f"{series.name} outliers",
            np.full(len(series.outliers), center),
            series.outliers,
            implot.Spec(
                line_color=color,
                marker_fill_color=color,
                marker_line_color=color,
                flags=implot.ItemFlags_.no_legend,
            ),
        )


def draw_curve(
    series: NumericDistribution, mode: int, color: imgui.ImVec4 | None = None
) -> bool:
    if mode == 1 and len(series.kde_y):
        implot.plot_line(
            series.name, series.kde_x, series.kde_y, implot.Spec(line_color=color)
        )
        return True
    if mode == 2 and len(series.ecdf_x):
        xs = np.concatenate(([series.ecdf_x[0]], series.ecdf_x))
        ys = np.concatenate(([0.0], series.ecdf_y))
        implot.plot_stairs(series.name, xs, ys, implot.Spec(line_color=color))
        return True
    return False


def show_comparison(
    comparison: Comparison,
    mode: int,
    fit: bool,
    *,
    title: str = "Column comparison",
    details: bool = True,
    height: float = 220,
    axes: AxisControls | None = None,
    colored: bool = False,
) -> bool:
    start_y = imgui.get_cursor_screen_pos().y
    settings = comparison.settings
    if not comparison.series:
        imgui.text_wrapped("Select numeric comparison columns in Plot settings.")
        return False
    if details:
        imgui.text(f"{'Z-score' if settings.standardize else 'Original'} units")
    if mode in (1, 2, 4) and any(s.sample_count < s.count for s in comparison.series):
        imgui.text_wrapped("Curves sampled: up to 2,000 finite values per column.")
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
        missing = [s.name for s in comparison.series if not len(s.kde_y)]
        if missing:
            names = ", ".join(missing[:3])
            if len(missing) > 3:
                names += f" and {len(missing) - 3} more"
            imgui.text_wrapped(f"Density unavailable: {names}. Try Histogram or ECDF.")
        if len(missing) == len(comparison.series):
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
    implot.setup_axes(
        "Column"
        if horizontal_boxes
        else "Z-score"
        if settings.standardize
        else "Value",
        "Z-score" if horizontal_boxes and settings.standardize else ylabel,
    )
    if horizontal_boxes:
        implot.setup_axis_ticks(
            implot.ImAxis_.x1,
            [float(i) for i in range(len(comparison.series))],
            [s.name for s in comparison.series],
        )
    if axes is not None:
        axes.apply()
    for i, series in enumerate(comparison.series):
        color = profile_color(series.name) if colored else None
        if mode == 0:
            hist_style = implot.Spec(line_color=color, fill_color=color, fill_alpha=0.2)
            hist_style.flags = implot.StairsFlags_.pre_step | implot.StairsFlags_.shaded
            implot.plot_stairs(
                series.name,
                np.concatenate(
                    ([comparison.edges[0]], comparison.edges, [comparison.edges[-1]])
                ),
                np.concatenate(([0, series.histogram[0]], series.histogram, [0])),
                hist_style,
            )
        elif mode in (1, 2):
            draw_curve(series, mode, color)
        elif horizontal_boxes and (mode == 3 or len(series.kde_y)):
            draw_box(series, i, mode == 4, color)
    if axes is not None:
        axes.observe()
    implot.end_plot()
    implot.pop_style_var()
    return True
