"""Shell widgets receive tab snapshots and navigation commands, never sessions."""

from collections.abc import Callable
from dataclasses import dataclass

from imgui_bundle import imgui

from datelier.gui.components.layout import Component, Container, FrameContext, Tab
from datelier.gui.components.native import label_text, target


@dataclass(frozen=True)
class FileTab:
    identity: str
    title: str
    active: bool

    @property
    def label(self) -> str:
        return label_text(self.title) + "###" + self.identity


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
        self.reorder = reorder
        self._active = ""
        self._order: tuple[str, ...] = ()

    def render(self, frame: FrameContext) -> None:
        if imgui.button("Undo"):
            self.undo()
        target(frame, "undo")
        imgui.same_line()
        if imgui.button("Redo"):
            self.redo()
        target(frame, "redo")
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
                lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
                frame.child(file.identity).record(
                    "close",
                    (
                        hi.x
                        - imgui.get_style().frame_padding.x
                        - imgui.get_font_size() / 2,
                        (lo.y + hi.y) / 2,
                    ),
                )
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
            # Track submitted tabs, so a file created by + (or by closing the
            # last tab) rebuilds the order next frame and keeps + at the end.
            self._order = order
            if imgui.tab_item_button("+###new", imgui.TabItemFlags_.no_reorder):
                self.new()
            target(frame, "new")
            if imgui.is_item_hovered():
                imgui.set_tooltip("New file")
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
