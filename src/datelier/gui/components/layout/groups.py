"""Small reusable groups keep optional controls contextual."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.gui.components.layout.base import Component, Container, FrameContext
from datelier.gui.components.native import target


class Conditional(Container):
    def __init__(
        self, key: str, visible: Callable[[], bool], children: tuple[Component, ...]
    ) -> None:
        super().__init__(key, children)
        self.visible = visible

    def render(self, frame: FrameContext) -> None:
        if self.visible():
            super().render(frame)


class Row(Container):
    """Immediate children share one row of compact commands."""

    def render(self, frame: FrameContext) -> None:
        for index, child in enumerate(self.children):
            if index:
                imgui.same_line()
            child.render(frame.child(child.key))


class Collapsible(Container):
    def __init__(self, key: str, label: str, children: tuple[Component, ...]) -> None:
        super().__init__(key, children)
        self.label = label

    def render(self, frame: FrameContext) -> None:
        opened = imgui.collapsing_header(self.label + "##" + self.key)
        target(frame, "toggle")
        if opened:
            super().render(frame)
