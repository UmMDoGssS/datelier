"""Contextual gesture help without permanent movement-instruction blocks."""

from imgui_bundle import imgui

from datelier.gui.components.base import Component, FrameContext
from datelier.gui.components.probe import GuiProbe, ViewScope


class ContextHelp(Component):
    def __init__(self, text: str) -> None:
        self.text = text

    def render(self, frame: FrameContext) -> None:
        imgui.text_disabled("(?)")
        if imgui.is_item_hovered():
            imgui.set_tooltip(self.text)


def show_help(text: str) -> None:
    ContextHelp(text).render(FrameContext(ViewScope(""), GuiProbe()))
