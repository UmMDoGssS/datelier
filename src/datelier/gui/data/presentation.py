"""Per-view style controls and pure prepared-cell color rendering."""

from dataclasses import dataclass, replace

from imgui_bundle import imgui

from datelier.inspection.presentation import (
    CellPresentation,
    NumericBounds,
    NumericScale,
    TablePresentation,
    cell_style,
)


@dataclass
class PresentationControls:
    settings: TablePresentation = TablePresentation()
    minimum: float = 0
    maximum: float = 1
    message: str = ""
    _bound: TablePresentation | None = None

    def show(self) -> None:
        if not imgui.collapsing_header("Cell presentation"):
            return
        saved = self.settings
        if self._bound != saved:
            self.minimum, self.maximum = saved.minimum, saved.maximum
        _, enabled = imgui.checkbox("Conditional cell colors", saved.enabled)
        imgui.same_line()
        _, badges = imgui.checkbox("Interpretation badges", saved.badges)
        scales = list(NumericScale)
        _, choice = imgui.combo(
            "Numeric scale", scales.index(saved.scale), [s.value for s in scales]
        )
        self.settings = replace(
            saved, enabled=enabled, badges=badges, scale=scales[choice]
        )
        self._bound = self.settings
        if self.settings.scale == NumericScale.CUSTOM:
            _, self.minimum = imgui.input_double("Shading minimum", self.minimum)
            _, self.maximum = imgui.input_double("Shading maximum", self.maximum)
            if imgui.button("Apply shading range"):
                candidate = replace(
                    self.settings, minimum=self.minimum, maximum=self.maximum
                )
                try:
                    candidate.validate()
                    self.settings = self._bound = candidate
                    self.message = ""
                except ValueError as error:
                    self.message = str(error)
        imgui.text_wrapped(
            "Blue to red: low to high. < / > mark values beyond the scale; "
            "= marks a flat scale. (null) marks null; ! marks nonfinite. "
            "Selected rows use selection color."
        )
        imgui.text_wrapped(self.message)


def draw_style(
    cell: CellPresentation,
    bounds: NumericBounds | None,
    settings: TablePresentation,
    selected: bool,
) -> str:
    style = cell_style(cell, bounds, settings)
    if style.rgba and not selected:
        light = imgui.get_style_color_vec4(imgui.Col_.window_bg).x > 0.5
        imgui.table_set_bg_color(
            imgui.TableBgTarget_.cell_bg,
            imgui.get_color_u32(imgui.ImVec4(*style.rgba, 0.25 if light else 0.35)),
        )
    return style.marker
