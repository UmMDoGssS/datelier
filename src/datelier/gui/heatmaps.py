"""Shared display controls and native colormaps, with no raw-value computation."""

from dataclasses import dataclass

import numpy as np
from imgui_bundle import imgui, implot

from datelier.inspection.heatmaps import RAMPS, Colormap, validate_range


@dataclass
class HeatmapControls:
    minimum: float = -1
    maximum: float = 1
    observed: tuple[float, float] | None = None
    initialized: bool = False
    message: str = ""

    def show(
        self,
        value_range: tuple[float, float] | None,
        colormap: Colormap,
        bounds: tuple[int | float, int | float] | None,
    ) -> tuple[tuple[float, float] | None, Colormap]:
        imgui.set_next_item_width(180)
        if imgui.begin_combo("Heatmap colors", colormap.value):
            for choice in Colormap:
                if imgui.selectable(choice.value, choice == colormap)[0]:
                    colormap = choice
            imgui.end_combo()
        if not self.initialized or value_range != self.observed:
            self._draft(value_range or bounds)
            self.initialized = True
        if imgui.collapsing_header("Heatmap display range"):
            imgui.text("Auto uses the prepared window's finite bounds.")
            if imgui.button("Auto window range"):
                value_range = None
                self._draft(bounds)
                self.message = ""
            imgui.same_line()
            if imgui.button("Use window bounds"):
                self._draft(bounds)
            imgui.set_next_item_width(140)
            _, self.minimum = imgui.input_double(
                "Display minimum", self.minimum, format="%.9g"
            )
            imgui.set_next_item_width(140)
            _, self.maximum = imgui.input_double(
                "Display maximum", self.maximum, format="%.9g"
            )
            if imgui.button("Apply display range"):
                candidate = self.minimum, self.maximum
                try:
                    validate_range(candidate)
                    value_range, self.message = candidate, ""
                except ValueError as error:
                    self.message = str(error)
            if self.message:
                imgui.text_wrapped(self.message)
        self.observed = value_range
        return value_range, colormap

    def _draft(self, bounds: tuple[int | float, int | float] | None) -> None:
        if bounds is None:
            self.minimum, self.maximum = -1, 1
            return
        lo, hi = (float(value) for value in bounds)
        if lo == hi:
            span = max(0.5, abs(lo) * 0.01)
            lo, hi = lo - span, hi + span
        self.minimum, self.maximum = lo, hi


def native_colormap(colormap: Colormap) -> int:
    name = "Datelier " + colormap.value
    index = implot.get_colormap_index(name)
    if index < 0:
        # Register the same linear stops used by worker RGBA preparation.
        colors = np.asarray([(*rgb, 1) for rgb in RAMPS[colormap]], dtype=np.float32)
        index = implot.add_colormap(name, colors, False)
    return index
