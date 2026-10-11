"""Stateless native box/violin geometry retained from the prior renderer."""

import numpy as np
from imgui_bundle import imgui, implot

from datelier.gui.components.native import label_text
from datelier.plotting.distributions import NumericDistribution


def box_label(name: str, index: int) -> str:
    return label_text(name) + f"##box/{index}"


def draw_box(
    series: NumericDistribution,
    index: int,
    violin: bool,
    color: imgui.ImVec4 | None = None,
) -> None:
    if series.box is None:
        return
    label = box_label(series.name, index)
    lo, q1, median, q3, hi = series.box
    center = float(index)
    if violin and len(series.kde_y):
        width = series.kde_y / series.kde_y.max() * 0.4
        xs = np.concatenate(
            (center - width, (center + width)[::-1], [center - width[0]])
        )
        ys = np.concatenate((series.kde_x, series.kde_x[::-1], series.kde_x[:1]))
        implot.plot_line(label, xs, ys, implot.Spec(line_color=color))
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
        implot.plot_line(label, xs, ys, implot.Spec(line_color=color))
    if len(series.outliers):
        implot.hide_next_item(
            not implot.internal.get_item(label).show, implot.Cond_.always
        )
        implot.plot_scatter(
            f"Outliers##{label}",
            np.full(len(series.outliers), center),
            series.outliers,
            implot.Spec(
                line_color=color,
                marker_fill_color=color,
                marker_line_color=color,
                flags=implot.ItemFlags_.no_legend,
            ),
        )
