"""Pair diagonals reuse the same prepared distribution series as column Profiles."""

from collections.abc import Callable

import numpy as np
from imgui_bundle import imgui, implot

from datelier.gui.components.layout import Component, Container, FrameContext
from datelier.gui.components.native import label_text
from datelier.gui.profiles.distributions import SERIES_TYPES
from datelier.plotting.distributions import Comparison
from datelier.plotting.relationships import Relationships


def distribution(data: Relationships | None, index: int) -> Comparison | None:
    return (
        data.diagonal_distributions[index]
        if data and index < len(data.diagonal_distributions)
        else None
    )


class CountDiagonal(Component):
    def __init__(
        self, prepared: Callable[[], Relationships | None], index: int
    ) -> None:
        super().__init__("counts")
        self.prepared, self.index = prepared, index

    def render(self, frame: FrameContext) -> None:
        data = self.prepared()
        if data is None:
            return
        bars = data.diagonals[self.index]
        if len(bars.counts):
            implot.plot_stairs(
                label_text(data.names[self.index]),
                np.concatenate(([bars.edges[0]], bars.edges, [bars.edges[-1]])),
                np.concatenate(([0, bars.counts[0]], bars.counts, [0])),
                implot.Spec(
                    flags=implot.StairsFlags_.pre_step | implot.StairsFlags_.shaded
                ),
            )


class DiagonalContent(Container):
    def __init__(
        self, prepared: Callable[[], Relationships | None], index: int
    ) -> None:
        super().__init__("diagonal", ())
        self.prepared, self.index = prepared, index
        self.routes = {
            0: CountDiagonal(prepared, index),
            **{
                mode: SERIES_TYPES[mode](lambda: distribution(prepared(), index))
                for mode in range(1, 5)
            },
        }

    def axes(self, name: str, mode: int) -> tuple[str, str]:
        return (
            ("", name)
            if mode in (3, 4)
            else (
                name,
                "Density" if mode == 1 else "Probability" if mode == 2 else "Rows",
            )
        )

    def render(self, frame: FrameContext) -> None:
        data = self.prepared()
        if data is None:
            return
        prepared = distribution(data, self.index)
        mode = data.diagonal_mode
        note = ""
        if mode and prepared is None:
            note = "Unavailable"
        elif prepared:
            series = prepared.series[0]
            if mode in (1, 4) and not len(series.kde_y):
                note = "Box (no density)" if mode == 4 and series.box else "No density"
            elif not series.count:
                note = "No values"
        self.children = (self.routes[mode],)
        super().render(frame)
        if note:
            pos = implot.get_plot_pos()
            implot.push_plot_clip_rect()
            implot.get_plot_draw_list().add_text(
                (pos.x + 5, pos.y + 5),
                imgui.get_color_u32(imgui.get_style_color_vec4(imgui.Col_.text)),
                note,
            )
            implot.pop_plot_clip_rect()

    def details(self, data: Relationships) -> str:
        if data.diagonal_mode == 0:
            return f"{data.names[self.index]} · all finite values · value / row count"
        prepared = distribution(data, self.index)
        if prepared is None:
            return data.diagonal_notes[self.index]
        series = prepared.series[0]
        return (
            f"{data.names[self.index]} · {series.count:,} finite values · "
            f"{series.sample_count:,} sampled for curves\n{series.note}"
        )

    def close(self) -> None:
        self.children = ()
        for child in self.routes.values():
            child.close()
