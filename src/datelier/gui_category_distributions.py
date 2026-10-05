"""Named category axes for prepared numeric box/violin relationships."""

from imgui_bundle import imgui, implot

from datelier.category_charts import CategoryChart, CategoryRepresentation
from datelier.gui_axes import AxisControls
from datelier.gui_distributions import draw_box
from datelier.gui_profile_colors import profile_color
from datelier.gui_table import TableView
from datelier.selection import LinkedSelection


def draw_category_distributions(
    chart: CategoryChart,
    selection: LinkedSelection,
    table: TableView,
    height: float,
    fit: bool,
    axes: AxisControls,
) -> tuple[bool, tuple[float, float]]:
    violin = chart.settings.representation == CategoryRepresentation.VIOLIN
    if fit:
        implot.set_next_axes_to_fit()
    implot.push_style_var(implot.StyleVar_.fit_padding, imgui.ImVec2(0.08, 0.05))
    if not implot.begin_plot(
        "##Category distributions", (-1, height), implot.Flags_.no_legend
    ):
        implot.pop_style_var()
        return False, (0, 0)
    implot.setup_axes(chart.settings.category, chart.value_label)
    implot.setup_axis_ticks(
        implot.ImAxis_.x1,
        [float(i) for i in range(len(chart.labels))],
        list(chart.labels),
    )
    axes.apply()
    for index, series in enumerate(chart.distributions):
        draw_box(series, index, violin, profile_color(series.name))
    first = chart.distributions[0]
    center = implot.plot_to_pixels(0, first.box[2] if first.box else 0)
    mouse = implot.get_plot_mouse_pos()
    index = round(mouse.x)
    if (
        implot.is_plot_hovered()
        and 0 <= index < len(chart.distributions)
        and abs(mouse.x - index) <= 0.4
    ):
        series = chart.distributions[index]
        if series.box is not None:
            low, q25, median, q75, high = series.box
            imgui.set_tooltip(
                f"{series.name} · {series.count:,} finite rows\n"
                f"25%: {q25:.6g} · Median: {median:.6g} · 75%: {q75:.6g}"
            )
            lo = float(series.kde_x[0]) if violin and len(series.kde_x) else low
            hi = float(series.kde_x[-1]) if violin and len(series.kde_x) else high
            lower = implot.plot_to_pixels(index, lo).y
            upper = implot.plot_to_pixels(index, hi).y
            hit = (
                min(lower, upper) - 5
                <= imgui.get_io().mouse_pos.y
                <= max(lower, upper) + 5
            )
            if hit and imgui.is_mouse_clicked(imgui.MouseButton_.left):
                ids = chart.row_ids[0][index]
                if selection.choose(
                    chart.revision, ids, toggle=imgui.get_io().key_ctrl
                ):
                    table.target_row = chart.first_positions[0][index] + 1
                    table.jump = True
                    if len(ids) < series.count:
                        selection.message += (
                            f" First {len(ids):,} of {series.count:,} matching rows."
                        )
    implot.get_input_map().pan = imgui.MouseButton_.middle
    axes.observe()
    implot.end_plot()
    implot.pop_style_var()
    return True, (center.x, center.y)
