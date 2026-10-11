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

    @property
    def label(self) -> str:
        return self.title.replace("##", "# #") + "###" + self.identity


def native_order(files: tuple[FileTab, ...]) -> tuple[str, ...]:
    """Read the native tab order at the isolated ImGui boundary."""
    identities = {imgui.get_id(file.label): file.identity for file in files}
    return tuple(
        identities[tab.id_]
        for tab in imgui.internal.get_current_tab_bar().tabs
        if tab.id_ in identities
    )


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
        reorder: Callable[[tuple[str, ...]], None],
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
        self.reorder = reorder
        self._active = ""
        self._order: tuple[str, ...] = ()

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
        target(frame, "redo")
        imgui.same_line()
        if imgui.button("Context"):
            self.toggle_context()
        target(frame, "context")
        imgui.same_line()
        if imgui.button("Table"):
            self.toggle_table()
        target(frame, "table")
        imgui.same_line()
        files = self.files()
        active = next((f.identity for f in files if f.active), "")
        changed = active != self._active
        if imgui.begin_tab_bar("files", imgui.TabBarFlags_.reorderable):
            desired = tuple(file.identity for file in files)
            if desired != self._order:
                native = imgui.internal.get_current_tab_bar()
                for identity in tuple(tab.id_ for tab in native.tabs):
                    imgui.internal.tab_bar_remove_tab(native, identity)
                changed = True
            for file in files:
                flags = (
                    imgui.TabItemFlags_.set_selected if changed and file.active else 0
                )
                opened, visible = imgui.begin_tab_item(file.label, True, flags)
                target(frame.child(file.identity), "tab")
                if imgui.is_item_clicked() or (
                    not changed and opened and active != file.identity
                ):
                    self.activate(file.identity)
                if opened:
                    imgui.end_tab_item()
                if not visible:
                    self.close_file(file.identity)
            current = self.files()
            order = native_order(current)
            if len(order) == len(current) and order != tuple(
                f.identity for f in current
            ):
                self.reorder(order)
            self._order = tuple(file.identity for file in self.files())
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
        self._scope: tuple[str, str] | None = None

    def render(self, frame: FrameContext) -> None:
        selected = self.selected()
        scope = frame.scope.file_id, frame.scope.view_id
        changed = selected != self._selected or scope != self._scope
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
                    if enabled and (
                        imgui.is_item_clicked() or not changed and tab.key != selected
                    ):
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
        # A child can navigate to another tab while this native row still shows
        # the previous tab. Observe the entry state so that command is applied
        # to the native tab bar next frame instead of being overwritten.
        self._selected = selected
        self._scope = scope
