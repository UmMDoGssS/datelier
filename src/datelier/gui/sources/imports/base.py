"""Import forms render only their immediate typed field/command children."""

from abc import ABC, abstractmethod

from imgui_bundle import imgui

from datelier.gui.components.base import Container, FrameContext


class OptionForm(Container, ABC):
    @property
    @abstractmethod
    def description(self) -> str: ...

    def render(self, frame: FrameContext) -> None:
        imgui.text_wrapped(self.description)
        super().render(frame)
