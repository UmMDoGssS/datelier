"""Finite-value, sampling, units and unavailable-density facts stay visible."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.gui.components.layout import Component, FrameContext
from datelier.plotting.distributions import Comparison


class DistributionFacts(Component):
    def __init__(
        self, prepared: Callable[[], Comparison | None], mode: Callable[[], int]
    ) -> None:
        super().__init__("distribution-facts")
        self.prepared, self.mode = prepared, mode

    def render(self, frame: FrameContext) -> None:
        data = self.prepared()
        if data is None:
            return
        imgui.text("Z-score units" if data.settings.standardize else "Original units")
        imgui.text_wrapped(
            "Histogram and box statistics include all finite values. "
            "KDE/ECDF/violin use up to 2,000 finite samples per column; "
            "displayed outliers use up to 150 sampled values."
        )
        if self.mode() in (1, 4):
            missing = [s.name for s in data.series if not len(s.kde_y)]
            if missing:
                imgui.text_wrapped(
                    "Density unavailable for "
                    + ", ".join(missing[:3])
                    + (f" and {len(missing) - 3} more" if len(missing) > 3 else "")
                    + ("; showing available boxes." if self.mode() == 4 else ".")
                )
