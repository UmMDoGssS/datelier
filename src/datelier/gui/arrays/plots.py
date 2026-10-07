"""Native vector/matrix rendering from bounded worker presentation buffers."""

import math

from imgui_bundle import imgui, implot

from datelier.gui.heatmaps import native_colormap
from datelier.inspection.arrays.slices import PreparedSlice


def plot_slice(data: PreparedSlice, fit: bool) -> bool:
    if data.numeric is None or data.numeric.size == 0 or not data.axes:
        return False
    imgui.text_wrapped(
        f"Finite range: {data.finite_range}. Plot conversion uses float64."
    )
    if len(data.axes) == 1:
        if fit:
            implot.set_next_axes_to_fit()
        if implot.begin_plot("Vector values", (-1, 230)):
            implot.setup_axes(f"Axis {data.axes[0]} index", "Value")
            implot.plot_line("Values", data.numeric, xstart=float(data.starts[0]))
            implot.end_plot()
            return True
    elif data.heatmap is not None:
        rows, columns = data.raw.shape
        if not rows or not columns:
            return False
        if implot.begin_plot("Matrix heatmap", (-1, 230), implot.Flags_.no_legend):
            row, column = data.starts
            implot.setup_axes(
                f"Axis {data.axes[1]} index", f"Axis {data.axes[0]} index"
            )
            implot.setup_axes_limits(
                column,
                column + columns,
                row,
                row + rows,
                imgui.Cond_.always if fit else imgui.Cond_.once,
            )
            implot.push_colormap(native_colormap(data.settings.colormap))
            implot.plot_heatmap(
                "Normalized colors",
                data.heatmap,
                0,
                1,
                "",
                implot.Point(column, row),
                implot.Point(column + columns, row + rows),
            )
            implot.pop_colormap()
            implot.push_plot_clip_rect()
            for y, start, count in data.nonfinite_spans:
                a = implot.plot_to_pixels(float(column + start), float(row + y))
                b = implot.plot_to_pixels(
                    float(column + start + count), float(row + y + 1)
                )
                implot.get_plot_draw_list().add_rect_filled(
                    imgui.ImVec2(min(a.x, b.x), min(a.y, b.y)),
                    imgui.ImVec2(max(a.x, b.x), max(a.y, b.y)),
                    0xFFFF00FF,
                )
            implot.pop_plot_clip_rect()
            if implot.is_plot_hovered():
                mouse = implot.get_plot_mouse_pos()
                y, x = math.floor(mouse.y) - row, math.floor(mouse.x) - column
                if 0 <= y < rows and 0 <= x < columns:
                    indices = list(data.settings.fixed or (0,) * len(data.source_shape))
                    indices[data.axes[0]] = row + y
                    indices[data.axes[1]] = column + x
                    imgui.set_tooltip(
                        f"Source index {tuple(indices)}: {data.cells[y][x]}"
                    )
            implot.end_plot()
            return True
    return False
