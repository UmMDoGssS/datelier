"""Native color-series legends and visibility for bounded scatter coordinates."""

from collections.abc import Callable

import numpy as np
from imgui_bundle import imgui, implot, implot3d
from numpy.typing import NDArray

from datelier.gui.components.native import label_text
from datelier.plotting.colors import ColorSeries
from datelier.plotting.scatter import Scatter


def rgba_color(rgba: int) -> imgui.ImVec4:
    return imgui.ImVec4(
        (rgba & 255) / 255,
        ((rgba >> 8) & 255) / 255,
        ((rgba >> 16) & 255) / 255,
        ((rgba >> 24) & 255) / 255,
    )


def item_label(points: Scatter, series: ColorSeries, index: int) -> str:
    label = label_text(series.label)
    source = points.colors.name if points.colors is not None else "Uniform"
    return f"{label}##{source}/{index}"


def draw_color_items(
    points: Scatter, selected: NDArray[np.bool_], *, three_d: bool = False
) -> NDArray[np.bool_]:
    colors = points.colors
    series = (
        colors.series
        if colors is not None
        else (
            ColorSeries("Rows", 0xFFE5A04C, np.arange(len(points.x), dtype=np.int64)),
        )
    )
    visible = np.zeros(len(points.x), dtype=bool)
    for i, group in enumerate(series):
        indices = group.indices[~selected[group.indices]]
        label = item_label(points, group, i)
        color = rgba_color(group.rgba)
        if three_d:
            assert points.z is not None
            style = implot3d.Spec(
                line_color=color,
                marker_fill_color=color,
                marker_line_color=color,
                marker=implot3d.Marker_.square,
                marker_size=1.5,
                line_weight=0,
            )
            if group.continuous and colors is not None:
                style.marker_fill_colors = style.marker_line_colors = colors.rgba[
                    indices
                ]
                style.flags = implot3d.ItemFlags_.no_legend
            if len(indices):
                implot3d.plot_scatter(
                    label,
                    points.x[indices],
                    points.y[indices],
                    points.z[indices],
                    style,
                )
            else:
                implot3d.plot_dummy(label, style)
            item = implot3d.internal.get_current_plot().items.get_item(label)
        else:
            style = implot.Spec(
                line_color=color,
                marker_fill_color=color,
                marker_line_color=color,
                marker=implot.Marker_.square,
                marker_size=2,
                line_weight=0,
            )
            if group.continuous and colors is not None:
                style.marker_fill_colors = style.marker_line_colors = colors.rgba[
                    indices
                ]
                style.flags = implot.ItemFlags_.no_legend
            if len(indices):
                implot.plot_scatter(label, points.x[indices], points.y[indices], style)
            else:
                implot.plot_dummy(label, style)
            item = implot.internal.get_item(label)
        if item.show:
            visible[group.indices] = True
    return visible


def legend_hovered(*, three_d: bool = False) -> bool:
    # Public visibility queries are absent from the pinned bindings. Isolate
    # their typed item/legend state here; hiding a native item must also hide
    # its selected overlay and prevent picking points behind the legend.
    legend = (
        implot3d.internal.get_current_plot().items.legend
        if three_d
        else implot.internal.get_current_plot().items.legend
    )
    return legend.rect_clamped.contains(imgui.get_io().mouse_pos)


def with_color_scale(
    points: Scatter, height: float, draw: Callable[[float], bool]
) -> bool:
    colors = points.colors
    if colors is None or colors.scale is None:
        return draw(-1)
    scale = colors.scale
    width = 85
    shown = draw(max(80, imgui.get_content_region_avail().x - width - 8))
    if not shown:
        return False
    # The 3D face control consumes part of the allocated area. Match the
    # actual native canvas so the bar's minimum tick stays inside the view.
    canvas_height = imgui.get_item_rect_size().y
    imgui.same_line()
    name = "Datelier continuous colors"
    cmap = implot.get_colormap_index(name)
    if cmap < 0:
        cmap = implot.add_colormap(
            name, np.array([0xFFF56432, 0xFF3264F5], dtype=np.uint32), False
        )
    label = (
        colors.name if scale.divisor == 1 else f"{colors.name} / {scale.divisor:.6g}"
    )
    implot.colormap_scale(
        label, scale.minimum, scale.maximum, (width, canvas_height), "%.4g", cmap=cmap
    )
    return shown
