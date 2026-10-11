"""Reusable range drafts with explicit validation before applying display state."""

from collections.abc import Callable

from datelier.gui.components.actions import CommandButton
from datelier.gui.components.inputs.fields import BooleanField, FloatField
from datelier.gui.components.layout import Container, FrameContext
from datelier.gui.components.layout.groups import Conditional
from datelier.inspection.heatmaps import validate_range


class DisplayRange(Container):
    def __init__(
        self,
        read: Callable[[], tuple[float, float] | None],
        write: Callable[[tuple[float, float] | None], None],
    ) -> None:
        self.read, self.write = read, write
        self.manual = False
        self.low, self.high = 0.0, 1.0
        self._observed: tuple[float, float] | None = None
        super().__init__(
            "display-range",
            (
                BooleanField(
                    "manual",
                    "Manual display range",
                    lambda: self.manual,
                    lambda value: setattr(self, "manual", value),
                ),
                Conditional(
                    "bounds",
                    lambda: self.manual,
                    (
                        FloatField(
                            "low",
                            "Minimum",
                            lambda: self.low,
                            lambda value: setattr(self, "low", value),
                            -1e300,
                            1e300,
                        ),
                        FloatField(
                            "high",
                            "Maximum",
                            lambda: self.high,
                            lambda value: setattr(self, "high", value),
                            -1e300,
                            1e300,
                        ),
                    ),
                ),
                CommandButton("apply", "Apply display range", self.apply),
            ),
        )

    def apply(self) -> None:
        value = (self.low, self.high) if self.manual else None
        validate_range(value)
        self.write(value)
        self._observed = value

    def render(self, frame: FrameContext) -> None:
        value = self.read()
        if value != self._observed:
            self._observed = value
            self.manual = value is not None
            self.low, self.high = value or (0, 1)
        super().render(frame)
