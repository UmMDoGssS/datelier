"""Render prepared profiles in value space or with explicit category names."""

import numpy as np
from imgui_bundle import imgui, implot

from datelier.plotting import Bars
from datelier.profiling import ColumnProfile, ProfileKind


def draw_histogram(name: str, bars: Bars) -> None:
    """Use every bin boundary; counts retain their original interval widths."""
    if not len(bars.counts):
        return
    style = implot.Spec()
    style.flags = implot.StairsFlags_.pre_step | implot.StairsFlags_.shaded
    implot.plot_stairs(
        name,
        np.concatenate(([bars.edges[0]], bars.edges, [bars.edges[-1]])),
        np.concatenate(([0, bars.counts[0]], bars.counts, [0])),
        style,
    )


def draw_profile(profile: ColumnProfile, bars: Bars, height: float = 170) -> bool:
    if not len(bars.counts):
        return False
    categories = profile.kind == ProfileKind.CATEGORICAL
    implot.push_style_var(implot.StyleVar_.fit_padding, imgui.ImVec2(0.1, 0.05))
    opened = implot.begin_plot(profile.name, (-1, height), implot.Flags_.no_legend)
    if not opened:
        implot.pop_style_var()
        return False
    if categories:
        implot.setup_axes("Rows", "", y_flags=implot.AxisFlags_.invert)
        implot.setup_axis_ticks(
            implot.ImAxis_.y1, bars.positions.tolist(), list(bars.labels)
        )
        style = implot.Spec()
        style.flags = implot.BarsFlags_.horizontal
        implot.plot_bars("Rows", bars.counts, bars.positions, 0.8, style)
    else:
        implot.setup_axes(profile.name, "Rows")
        if bars.tick_labels:
            stride = max(1, (len(bars.edges) - 1 + 3) // 4)
            indices = list(range(0, len(bars.edges) - 1, stride)) + [
                len(bars.edges) - 1
            ]
            implot.setup_axis_ticks(
                implot.ImAxis_.x1,
                [float(bars.edges[i]) for i in indices],
                [bars.tick_labels[i] for i in indices],
            )
        draw_histogram("Rows", bars)
    implot.end_plot()
    implot.pop_style_var()
    return True
