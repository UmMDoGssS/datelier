"""Typed field components with uniform labels and available-width sizing."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.gui.components.base import Component, FrameContext
from datelier.gui.components.native import target


class ChoiceField[T](Component):
    def __init__(
        self,
        key: str,
        label: str,
        choices: tuple[T, ...],
        get: Callable[[], T],
        set_value: Callable[[T], None],
        labels: tuple[str, ...] | None = None,
    ) -> None:
        super().__init__(key)
        self.label, self.choices, self.get, self.set_value = (
            label,
            choices,
            get,
            set_value,
        )
        self.labels = labels or tuple(str(c) for c in choices)

    def render(self, frame: FrameContext) -> None:
        imgui.text(self.label)
        imgui.set_next_item_width(-1)
        value = self.get()
        changed, index = imgui.combo(
            "##" + self.key,
            self.choices.index(value) if value in self.choices else 0,
            list(self.labels),
        )
        target(frame, "value")
        if changed:
            self.set_value(self.choices[index])


class BooleanField(Component):
    def __init__(
        self,
        key: str,
        label: str,
        get: Callable[[], bool],
        set_value: Callable[[bool], None],
    ) -> None:
        super().__init__(key)
        self.label, self.get, self.set_value = label, get, set_value

    def render(self, frame: FrameContext) -> None:
        changed, value = imgui.checkbox(self.label + "##" + self.key, self.get())
        target(frame, "value")
        if changed:
            self.set_value(value)


class IntegerField(Component):
    def __init__(
        self,
        key: str,
        label: str,
        get: Callable[[], int],
        set_value: Callable[[int], None],
        minimum: int = 0,
        maximum: int = 2**31 - 1,
    ) -> None:
        super().__init__(key)
        self.label, self.get, self.set_value = label, get, set_value
        self.minimum, self.maximum = minimum, maximum

    def render(self, frame: FrameContext) -> None:
        imgui.text(self.label)
        imgui.set_next_item_width(-1)
        changed, value = imgui.input_int("##" + self.key, self.get())
        target(frame, "value")
        if changed:
            self.set_value(max(self.minimum, min(self.maximum, value)))


class FloatField(Component):
    def __init__(
        self,
        key: str,
        label: str,
        get: Callable[[], float],
        set_value: Callable[[float], None],
        minimum: float = 0,
        maximum: float = 1e9,
    ) -> None:
        super().__init__(key)
        self.label, self.get, self.set_value = label, get, set_value
        self.minimum, self.maximum = minimum, maximum

    def render(self, frame: FrameContext) -> None:
        imgui.text(self.label)
        imgui.set_next_item_width(-1)
        changed, value = imgui.input_double("##" + self.key, self.get())
        target(frame, "value")
        if changed:
            self.set_value(max(self.minimum, min(self.maximum, value)))


class TextField(Component):
    def __init__(
        self,
        key: str,
        label: str,
        get: Callable[[], str],
        set_value: Callable[[str], None],
        multiline: bool = False,
    ) -> None:
        super().__init__(key)
        self.label, self.get, self.set_value, self.multiline = (
            label,
            get,
            set_value,
            multiline,
        )

    def render(self, frame: FrameContext) -> None:
        imgui.text(self.label)
        imgui.set_next_item_width(-1)
        if self.multiline:
            changed, value = imgui.input_text_multiline(
                "##" + self.key, self.get(), (-1, 80)
            )
        else:
            changed, value = imgui.input_text("##" + self.key, self.get())
        target(frame, "value")
        if changed:
            self.set_value(value)
