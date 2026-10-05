"""Editable numeric 2D axis ranges, applied once so native pan/zoom stays free."""

import math
from dataclasses import dataclass, field

from imgui_bundle import imgui, implot

from datelier.gui.widgets.fields import combo

Range = tuple[float, float]
SCALES = [implot.Scale_.linear, implot.Scale_.sym_log, implot.Scale_.log10]


def validate_range(bounds: Range, logarithmic: bool = False) -> None:
    lo, hi = bounds
    if not all(math.isfinite(v) for v in bounds) or lo >= hi:
        raise ValueError("Minimum and maximum must be finite, with minimum < maximum.")
    if logarithmic and lo <= 0:
        raise ValueError("Log scale requires a positive minimum.")


@dataclass
class AxisControls:
    enabled: tuple[bool, bool] = (True, True)
    limits: tuple[Range, Range] = ((0, 1), (0, 1))
    scales: list[int] = field(default_factory=lambda: [0, 0])
    draft: list[list[float]] = field(default_factory=lambda: [[0, 1], [0, 1]])
    draft_scales: list[int] = field(default_factory=lambda: [0, 0])
    pending: bool = False
    error: str = ""
    open_pixel: tuple[float, float] = (0, 0)
    apply_pixel: tuple[float, float] = (0, 0)

    def accept(self) -> None:
        ranges = [
            (v[0], v[1]) if self.enabled[i] else self.limits[i]
            for i, v in enumerate(self.draft)
        ]
        scales = [
            self.draft_scales[i] if enabled else self.scales[i]
            for i, enabled in enumerate(self.enabled)
        ]
        for i, enabled in enumerate(self.enabled):
            if enabled:
                if not 0 <= scales[i] < len(SCALES):
                    raise ValueError("Unknown axis scale.")
                validate_range(ranges[i], scales[i] == 2)
        self.limits = (ranges[0], ranges[1])
        self.scales = scales
        self.pending = True
        self.error = ""

    def show(self) -> None:
        opened = imgui.button("Axes")
        pos, size = imgui.get_item_rect_min(), imgui.get_item_rect_size()
        self.open_pixel = (pos.x + size.x / 2, pos.y + size.y / 2)
        if opened:
            self.draft = [list(v) for v in self.limits]
            self.draft_scales = self.scales.copy()
            self.error = ""
            imgui.open_popup("Axis ranges")
        if imgui.begin_popup("Axis ranges"):
            for i, enabled in enumerate(self.enabled):
                if not enabled:
                    continue
                axis = "XY"[i]
                choices = ["Linear", "Symmetric log"]
                if self.draft[i][0] > 0 or self.draft_scales[i] == 2:
                    choices.append("Log 10")
                _, self.draft_scales[i] = combo(
                    f"{axis} scale", self.draft_scales[i], choices
                )
                if imgui.begin_table(
                    f"{axis} range", 2, imgui.TableFlags_.sizing_stretch_same
                ):
                    imgui.table_next_row()
                    for j, label in enumerate(("Minimum", "Maximum")):
                        imgui.table_set_column_index(j)
                        imgui.text(f"{axis} {label.lower()}")
                        imgui.set_next_item_width(120)
                        _, self.draft[i][j] = imgui.input_double(
                            f"##{axis} {label}", self.draft[i][j], format="%.6g"
                        )
                    imgui.end_table()
            apply = imgui.button("Apply ranges")
            pos, size = imgui.get_item_rect_min(), imgui.get_item_rect_size()
            self.apply_pixel = (pos.x + size.x / 2, pos.y + size.y / 2)
            if apply:
                try:
                    self.accept()
                    imgui.close_current_popup()
                except ValueError as error:
                    self.error = str(error)
            if self.error:
                imgui.text_wrapped(self.error)
            imgui.end_popup()

    def apply(self) -> None:
        for i, axis in enumerate((implot.ImAxis_.x1, implot.ImAxis_.y1)):
            if self.enabled[i]:
                implot.setup_axis_scale(axis, SCALES[self.scales[i]])
                if self.pending:
                    implot.setup_axis_limits(axis, *self.limits[i], imgui.Cond_.always)
        self.pending = False

    def observe(self) -> None:
        limits = implot.get_plot_limits()
        self.limits = ((limits.x.min, limits.x.max), (limits.y.min, limits.y.max))
