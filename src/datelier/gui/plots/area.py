"""Plot axes/camera controls over the shared content viewport."""

from collections.abc import Callable
from dataclasses import dataclass, field

from imgui_bundle import imgui

from datelier.gui.components.viewport import ResizableViewport
from datelier.gui.plots.axes import AxisControls


@dataclass
class PlotArea(ResizableViewport):
    axes: AxisControls = field(default_factory=AxisControls)

    def show(
        self,
        label: str,
        key: object,
        draw: Callable[[float, bool, AxisControls], bool],
        *,
        numeric_axes: tuple[bool, bool] = (True, True),
        three_d: bool = False,
        minimum_height: float = 170,
        footer: Callable[[], None] | None = None,
        footer_height: float = 0,
    ) -> bool:
        if key != self._key:
            self.axes = AxisControls(enabled=numeric_axes)

        def toolbar() -> None:
            if any(numeric_axes) or three_d:
                imgui.same_line()
                if imgui.button("Fit axes"):
                    self.fit = True
                    self.axes.pending = False
            if any(numeric_axes) and not three_d:
                imgui.same_line()
                self.axes.show()

        return self.show_content(
            label,
            key,
            lambda height, fit: draw(height, fit, self.axes),
            toolbar=toolbar,
            minimum_height=minimum_height,
            footer=footer,
            footer_height=footer_height,
        )
