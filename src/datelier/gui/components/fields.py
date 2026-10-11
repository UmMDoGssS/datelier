"""Typed field components with uniform labels and available-width sizing."""

from abc import ABC, abstractmethod
from collections.abc import Callable

from imgui_bundle import imgui

from datelier.gui.components.base import Component, FrameContext
from datelier.gui.components.native import target


class Field(Component, ABC):
    """Repeated field names remain independent inside different component groups."""

    def render(self, frame: FrameContext) -> None:
        imgui.push_id("/".join(frame.path))
        try:
            self.render_field(frame)
        finally:
            imgui.pop_id()

    @abstractmethod
    def render_field(self, frame: FrameContext) -> None: ...


class ChoiceField[T](Field):
    def __init__(
        self,
        key: str,
        label: str,
        choices: tuple[T, ...] | Callable[[], tuple[T, ...]],
        get: Callable[[], T],
        set_value: Callable[[T], None],
        labels: tuple[str, ...] | Callable[[], tuple[str, ...]] | None = None,
    ) -> None:
        super().__init__(key)
        self.label, self.choices, self.get, self.set_value = (
            label,
            choices,
            get,
            set_value,
        )
        self.labels = labels

    def render_field(self, frame: FrameContext) -> None:
        imgui.text(self.label)
        imgui.set_next_item_width(-1)
        value = self.get()
        choices = self.choices() if callable(self.choices) else self.choices
        if not choices:
            imgui.text_disabled("No available choices")
            return
        labels = (self.labels() if callable(self.labels) else self.labels) or tuple(
            str(c) for c in choices
        )
        changed, index = imgui.combo(
            "##" + self.key,
            choices.index(value) if value in choices else 0,
            list(labels),
        )
        target(frame, "value")
        if changed:
            self.set_value(choices[index])


class BooleanField(Field):
    def __init__(
        self,
        key: str,
        label: str,
        get: Callable[[], bool],
        set_value: Callable[[bool], None],
    ) -> None:
        super().__init__(key)
        self.label, self.get, self.set_value = label, get, set_value

    def render_field(self, frame: FrameContext) -> None:
        changed, value = imgui.checkbox(self.label + "##" + self.key, self.get())
        target(frame, "value")
        if changed:
            self.set_value(value)


class IntegerField(Field):
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

    def render_field(self, frame: FrameContext) -> None:
        imgui.text(self.label)
        imgui.set_next_item_width(-1)
        changed, value = imgui.input_int("##" + self.key, self.get())
        target(frame, "value")
        if changed:
            self.set_value(max(self.minimum, min(self.maximum, value)))


class FloatField(Field):
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

    def render_field(self, frame: FrameContext) -> None:
        imgui.text(self.label)
        imgui.set_next_item_width(-1)
        changed, value = imgui.input_double("##" + self.key, self.get())
        target(frame, "value")
        if changed:
            self.set_value(max(self.minimum, min(self.maximum, value)))


class TextField(Field):
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

    def render_field(self, frame: FrameContext) -> None:
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
