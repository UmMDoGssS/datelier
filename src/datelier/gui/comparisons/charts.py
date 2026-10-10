"""Bounded native numeric overlays and common-order category bars."""

import numpy as np
from imgui_bundle import imgui, implot

from datelier.core.column_roles import ColumnRole
from datelier.gui.plots.scatter_items import legend_hovered
from datelier.gui.profiles.colors import profile_color
from datelier.inspection.comparison_settings import Normalization
from datelier.inspection.comparisons.types import PreparedComparison


def draw_chart(
    result: PreparedComparison, selected_source: int, fit: bool, height: float = 260
) -> tuple[bool, int | None]:
    numeric = result.kind == ColumnRole.NUMERIC
    if fit:
        implot.set_next_axes_to_fit()
    implot.push_style_var(implot.StyleVar_.fit_padding, imgui.ImVec2(0.05, 0.1))
    if not implot.begin_plot("File profiles", (-1, height)):
        implot.pop_style_var()
        return False, None
    normalized = result.settings.normalization == Normalization.DENSITY
    x_label = "Value" if numeric else "Proportion" if normalized else "Rows"
    if numeric and result.scale != 1:
        x_label += f" / {result.scale:.6g}"
    implot.setup_axes(
        x_label,
        "Density" if numeric and normalized else "Rows" if numeric else "Category",
    )
    implot.setup_legend(
        implot.Location_.north,
        implot.LegendFlags_.outside | implot.LegendFlags_.horizontal,
    )
    if not numeric:
        implot.setup_axis_ticks(
            implot.ImAxis_.y1,
            [float(i) for i in range(len(result.labels))],
            list(result.labels),
        )
    labels: list[str] = []
    width = 0.8 / len(result.series)
    for index, series in enumerate(result.series):
        label = (
            f"{series.label} / {series.origin.column}".replace("##", "#\u200b#")
            + f"##{series.origin.file_id}"
        )
        labels.append(label)
        color = (
            imgui.ImVec4(*series.color)
            if series.color
            else profile_color(series.origin.file_id)
        )
        style = implot.Spec(
            line_color=color, fill_color=color, fill_alpha=0.28 if numeric else 0.9
        )
        if numeric:
            xs = np.repeat(np.asarray(result.edges), 2)
            ys = np.concatenate(([0], np.repeat(series.heights, 2), [0]))
            implot.plot_shaded(label, xs, ys, spec=style)
            implot.hide_next_item(
                not implot.internal.get_item(label).show, implot.Cond_.always
            )
            implot.plot_line(
                "Outline##" + series.origin.file_id,
                xs,
                ys,
                implot.Spec(line_color=color, flags=implot.ItemFlags_.no_legend),
            )
        else:
            style.flags = implot.BarsFlags_.horizontal
            ys = (
                np.arange(len(result.labels), dtype=np.float64)
                - 0.4
                + width * (index + 0.5)
            )
            implot.plot_bars(label, series.heights, ys, width, style)
    chosen = None
    if (
        implot.is_plot_hovered()
        and not legend_hovered()
        and implot.internal.get_item(labels[selected_source]).show
    ):
        mouse = implot.get_plot_mouse_pos()
        index = (
            int(np.searchsorted(result.edges, mouse.x, side="left") - 1)
            if numeric
            else int(np.floor(mouse.y + 0.5))
        )
        if numeric and mouse.x == result.edges[0]:
            index = 0
        series = result.series[selected_source]
        if 0 <= index < len(series.counts):
            imgui.set_tooltip(
                f"{series.label}: {series.counts[index]:,} source rows\n"
                "Click to select in this file (up to 10,000)."
            )
            if imgui.is_mouse_clicked(imgui.MouseButton_.left):
                chosen = index
    implot.get_input_map().pan = imgui.MouseButton_.middle
    implot.end_plot()
    implot.pop_style_var()
    return True, chosen
