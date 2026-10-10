"""Shell widgets receive tab snapshots and navigation commands, never sessions."""

from collections.abc import Callable
from dataclasses import dataclass

from imgui_bundle import imgui

from datelier.gui.components.base import Component, Container, FrameContext, Tab
from datelier.gui.components.native import target


@dataclass(frozen=True)
class FileTab:
    identity: str
    title: str
    active: bool


class FileTabs(Component):
    def __init__(
        self,
        files: Callable[[], tuple[FileTab, ...]],
        activate: Callable[[str], None],
        close: Callable[[str], None],
        new: Callable[[], object],
        undo: Callable[[], None],
        redo: Callable[[], None],
        toggle_context: Callable[[], None],
        toggle_table: Callable[[], None],
    ) -> None:
        super().__init__("files")
        self.files, self.activate, self.close_file, self.new = (
            files,
            activate,
            close,
            new,
        )
        self.undo, self.redo = undo, redo
        self.toggle_context, self.toggle_table = toggle_context, toggle_table
        self._active = ""

    def render(self, frame: FrameContext) -> None:
        if imgui.button("+"):
            self.new()
        target(frame, "new")
        imgui.same_line()
        if imgui.button("Undo"):
            self.undo()
        target(frame, "undo")
        imgui.same_line()
        if imgui.button("Redo"):
            self.redo()
        imgui.same_line()
        if imgui.button("Context"):
            self.toggle_context()
        imgui.same_line()
        if imgui.button("Table"):
            self.toggle_table()
        imgui.same_line()
        files = self.files()
        active = next((f.identity for f in files if f.active), "")
        changed = active != self._active
        if imgui.begin_tab_bar("files", imgui.TabBarFlags_.reorderable):
            for file in files:
                flags = (
                    imgui.TabItemFlags_.set_selected if changed and file.active else 0
                )
                opened, visible = imgui.begin_tab_item(
                    file.title + "##" + file.identity, True, flags
                )
                target(frame.child(file.identity), "tab")
                if imgui.is_item_clicked() or (opened and active != file.identity):
                    self.activate(file.identity)
                if opened:
                    imgui.end_tab_item()
                if not visible:
                    self.close_file(file.identity)
            imgui.end_tab_bar()
        self._active = active


class NamedTab(Tab):
    def __init__(
        self, label: str, content: Component, enabled: Callable[[], bool] = lambda: True
    ) -> None:
        super().__init__(label, (content,))
        self.label = label
        self.enabled = enabled


class CanvasTabs(Container):
    def __init__(
        self,
        tabs: tuple[NamedTab, ...],
        selected: Callable[[], str],
        choose: Callable[[str], None],
    ) -> None:
        super().__init__("canvas", tabs)
        self.selected, self.choose = selected, choose
        self._selected = ""

    def render(self, frame: FrameContext) -> None:
        selected = self.selected()
        changed = selected != self._selected
        if imgui.begin_tab_bar("canvas"):
            for tab in self.children:
                flags = (
                    imgui.TabItemFlags_.set_selected
                    if changed and tab.key == selected
                    else 0
                )
                enabled = tab.enabled() if isinstance(tab, NamedTab) else True
                imgui.begin_disabled(not enabled)
                opened, _ = imgui.begin_tab_item(tab.key, None, flags)
                target(frame.child(tab.key), "tab")
                if opened:
                    self.choose(tab.key)
                    if enabled:
                        tab.render(frame.child(tab.key))
                    else:
                        imgui.text_wrapped(
                            "Switch to a file inspection view to edit its data."
                        )
                    imgui.end_tab_item()
                imgui.end_disabled()
            imgui.end_tab_bar()
        self._selected = self.selected()
