"""Menus compose direct action components with injected commands."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.gui.components.layout import Component, Container, FrameContext
from datelier.gui.components.native import label_text, target
from datelier.workspace.recent import RecentSource


class MenuAction(Component):
    def __init__(
        self,
        key: str,
        label: str,
        command: Callable[[], object],
        selected: Callable[[], bool] = lambda: False,
        shortcut: str = "",
    ) -> None:
        super().__init__(key)
        self.label, self.command, self.selected, self.shortcut = (
            label,
            command,
            selected,
            shortcut,
        )

    def render(self, frame: FrameContext) -> None:
        label = label_text(self.label) + "###" + self.key
        if imgui.menu_item(label, self.shortcut, self.selected())[0]:
            self.command()
        target(frame, "run")
        if imgui.is_item_hovered() and len(self.label) > 80:
            imgui.set_tooltip(self.label)


class Menu(Container):
    def render(self, frame: FrameContext) -> None:
        opened = imgui.begin_menu(self.key)
        target(frame, "menu")
        if opened:
            super().render(frame)
            imgui.end_menu()


class MenuBar(Container):
    def __init__(self, children: tuple[Menu, ...]) -> None:
        super().__init__("menus", children)


class RecentMenu(Menu):
    def __init__(
        self,
        entries: Callable[[], tuple[RecentSource, ...]],
        open_source: Callable[[RecentSource], None],
    ) -> None:
        super().__init__("Recent", ())
        self.entries, self.open_source = entries, open_source

    def render(self, frame: FrameContext) -> None:
        self.children = tuple(
            MenuAction(
                str(i), source.path, lambda source=source: self.open_source(source)
            )
            for i, source in enumerate(self.entries())
        )
        super().render(frame)
