"""Conditional categorical controls and named aggregate bars."""

from dataclasses import dataclass, field

import numpy as np
from imgui_bundle import imgui, implot

from datelier.category_charts import CategoryChart, CategoryRepresentation
from datelier.dataset import Dataset
from datelier.exploration import Explorer
from datelier.gui_axes import AxisControls
from datelier.gui_fields import combo
from datelier.gui_plot_area import PlotArea
from datelier.gui_plot_controls import PlotControls
from datelier.gui_table import TableView
from datelier.selection import LinkedSelection


@dataclass
class CategoryView:
    area: PlotArea = field(default_factory=PlotArea)
    bar_pixel: tuple[float, float] = (0, 0)
    selected_rows: int = 0
    plot_frames: int = 0

    def controls(
        self, plots: PlotControls, explorer: Explorer, dataset: Dataset
    ) -> bool:
        choices = ["Scatter"]
        if plots.categories:
            choices.append(CategoryRepresentation.COUNTS.value)
            if len(plots.categories) > 1:
                choices.append(CategoryRepresentation.GROUPED.value)
            if plots.numeric:
                choices.extend(
                    [
                        CategoryRepresentation.MEAN.value,
                        CategoryRepresentation.MEDIAN.value,
                        CategoryRepresentation.SUM.value,
                    ]
                )
        if plots.relationship_chart not in choices:
            plots.relationship_chart = "Scatter"
        changed, index = combo(
            "Chart type", choices.index(plots.relationship_chart), choices
        )
        plots.relationship_chart = choices[index]
        categorical = plots.relationship_chart != "Scatter"
        if categorical:
            fields = (
                1 if plots.relationship_chart == CategoryRepresentation.COUNTS else 2
            )
            if imgui.begin_table(
                "Category fields", fields, imgui.TableFlags_.sizing_stretch_same
            ):
                imgui.table_next_row()
                imgui.table_set_column_index(0)
                picked, index = combo(
                    "Category",
                    plots.categories.index(
                        plots.category_column or plots.categories[0]
                    ),
                    list(plots.categories),
                )
                changed |= picked
                plots.category_column = plots.categories[index]
                if fields == 2:
                    imgui.table_set_column_index(1)
                if plots.relationship_chart == CategoryRepresentation.GROUPED:
                    groups = [n for n in plots.categories if n != plots.category_column]
                    picked, index = combo(
                        "Group by",
                        groups.index(plots.category_group)
                        if plots.category_group in groups
                        else 0,
                        groups,
                    )
                    changed |= picked
                    plots.category_group = groups[index]
                elif plots.relationship_chart != CategoryRepresentation.COUNTS:
                    picked, index = combo(
                        "Value",
                        plots.numeric.index(plots.category_value or plots.numeric[0]),
                        list(plots.numeric),
                    )
                    changed |= picked
                    plots.category_value = plots.numeric[index]
                imgui.end_table()
        if changed:
            try:
                explorer.request(dataset, plots.settings())
                plots.error = ""
            except ValueError as error:
                plots.error = str(error)
        if plots.error:
            imgui.text_wrapped(plots.error)
        return categorical

    def show(
        self, chart: CategoryChart, selection: LinkedSelection, table: TableView
    ) -> bool:
        if not chart.labels:
            imgui.text("No values to plot.")
            return False
        if chart.input_rows != chart.total_rows:
            imgui.text(
                f"First {chart.input_rows:,} of {chart.total_rows:,} rows (sample)"
            )
        if chart.excluded_values:
            imgui.text(
                f"{chart.excluded_values:,} missing or nonfinite values excluded"
            )
        shown = self.area.show(
            "Category plot",
            (chart.revision, chart.settings),
            lambda height, fit, axes: self.draw(
                chart, selection, table, height, fit, axes
            ),
            numeric_axes=(True, False),
        )
        if shown:
            self.plot_frames += 1
        return shown

    def draw(
        self,
        chart: CategoryChart,
        selection: LinkedSelection,
        table: TableView,
        height: float,
        fit: bool,
        axes: AxisControls,
    ) -> bool:
        if fit:
            implot.set_next_axes_to_fit()
        title = f"{chart.value_label} by {chart.settings.category}"
        flags = implot.Flags_.no_legend if len(chart.groups) == 1 else 0
        if not implot.begin_plot(title, (-1, height), flags):
            return False
        implot.setup_axes(
            chart.value_label, chart.settings.category, y_flags=implot.AxisFlags_.invert
        )
        if len(chart.groups) > 1:
            implot.setup_legend(
                implot.Location_.north,
                implot.LegendFlags_.outside | implot.LegendFlags_.horizontal,
            )
        positions = np.arange(len(chart.labels), dtype=np.float64)
        implot.setup_axis_ticks(
            implot.ImAxis_.y1, positions.tolist(), list(chart.labels)
        )
        axes.apply()
        width = 0.8 / len(chart.groups)
        for g, name in enumerate(chart.groups):
            ys = positions - 0.4 + width * (g + 0.5)
            style = implot.Spec()
            style.flags = implot.BarsFlags_.horizontal
            implot.plot_bars(name, chart.values[g], ys, width, style)
        pixel = implot.plot_to_pixels(float(chart.values[0, 0]) / 2, -0.4 + width * 0.5)
        self.bar_pixel = (pixel.x, pixel.y)
        mouse = implot.get_plot_mouse_pos()
        self.selected_rows = (
            len(selection.row_ids) if selection.revision == chart.revision else 0
        )
        if implot.is_plot_hovered():
            c = int(np.floor(mouse.y + 0.5))
            g = int(np.floor((mouse.y - c + 0.4) / width))
            if (
                0 <= c < len(chart.labels)
                and 0 <= g < len(chart.groups)
                and chart.counts[g, c]
            ):
                value = chart.values[g, c]
                if min(0, value) <= mouse.x <= max(0, value):
                    imgui.set_tooltip(
                        f"{chart.labels[c]} · {chart.groups[g]}\n"
                        f"{chart.value_label}: {value:,.6g}\n"
                        f"{chart.counts[g, c]:,} rows"
                    )
                    if imgui.is_mouse_clicked(imgui.MouseButton_.left):
                        ids = chart.row_ids[g][c]
                        if selection.choose(
                            chart.revision, ids, toggle=imgui.get_io().key_ctrl
                        ):
                            table.target_row = chart.first_positions[g][c] + 1
                            table.jump = True
                            if len(ids) < chart.counts[g, c]:
                                selection.message += (
                                    f" First {len(ids):,} of {chart.counts[g, c]:,} "
                                    "matching rows."
                                )
        implot.get_input_map().pan = imgui.MouseButton_.middle
        axes.observe()
        implot.end_plot()
        return True
