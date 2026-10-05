"""Render worker-prepared diagonal distributions inside a pair-grid cell."""

from imgui_bundle import imgui, implot

from datelier.gui.plots.distributions import draw_box, draw_curve
from datelier.gui.profiles.view import draw_histogram
from datelier.plotting.relationships import Relationships


def diagonal_axes(name: str, mode: int) -> tuple[str, str]:
    if mode in (3, 4):
        return "", name
    return name, "Density" if mode == 1 else "Probability" if mode == 2 else "Rows"


def _note(text: str) -> None:
    pos = implot.get_plot_pos()
    implot.push_plot_clip_rect()
    implot.get_plot_draw_list().add_text(
        imgui.ImVec2(pos.x + 5, pos.y + 5),
        imgui.get_color_u32(imgui.get_style_color_vec4(imgui.Col_.text)),
        text,
    )
    implot.pop_plot_clip_rect()


def draw_diagonal(data: Relationships, index: int) -> None:
    mode = data.diagonal_mode
    if mode == 0:
        draw_histogram(data.names[index], data.diagonals[index])
        return
    prepared = data.diagonal_distributions[index]
    if prepared is None:
        _note("Unavailable")
        return
    series = prepared.series[0]
    if mode in (1, 2):
        if not draw_curve(series, mode):
            _note("No density" if series.count else "No values")
    elif series.box is not None:
        draw_box(series, 0, mode == 4)
        if mode == 4 and not len(series.kde_y):
            _note("Box (no density)")
    else:
        _note("No values")


def diagonal_details(data: Relationships, index: int) -> str:
    name = data.names[index]
    if data.diagonal_mode == 0:
        return f"{name}: value / row count\nAll finite values"
    prepared = data.diagonal_distributions[index]
    if prepared is None:
        return f"{name}: {data.diagonal_notes[index]}"
    series = prepared.series[0]
    summary = f"{name}: {series.count:,} finite values"
    if data.diagonal_mode in (1, 2, 4):
        summary += f" · {series.sample_count:,} sampled for curves"
    return summary + "\n" + series.note
