"""Menus and an explicit open command, independent of editor internals."""

from collections.abc import Callable
from pathlib import Path

from imgui_bundle import imgui

from datelier.gui.components.base import Component, FrameContext
from datelier.gui.components.native import target


class OpenDialog(Component):
    def __init__(self, open_paths: Callable[[tuple[Path, ...]], None]) -> None:
        super().__init__("open")
        self.open_paths = open_paths
        self.requested = False
        self.paths = ""

    def render(self, frame: FrameContext) -> None:
        if self.requested:
            imgui.open_popup("Open sources")
            self.requested = False
        imgui.set_next_window_size((600, 260), imgui.Cond_.appearing)
        opened, _ = imgui.begin_popup_modal("Open sources", True)
        if opened:
            imgui.text("File or folder paths, one per line")
            _, self.paths = imgui.input_text_multiline("##paths", self.paths, (-1, 130))
            if imgui.button("Open"):
                paths = tuple(
                    Path(p.strip()) for p in self.paths.splitlines() if p.strip()
                )
                if paths:
                    self.open_paths(paths)
                    imgui.close_current_popup()
            target(frame, "submit")
            imgui.same_line()
            if imgui.button("Cancel"):
                imgui.close_current_popup()
            imgui.end_popup()


class MenuBar(Component):
    def __init__(
        self,
        open_dialog: Callable[[], None],
        reset_layout: Callable[[], None],
        quit_app: Callable[[], None],
        export_dialog: Callable[[], None],
    ) -> None:
        super().__init__("menus")
        self.export_dialog = export_dialog
        self.open_dialog, self.reset_layout, self.quit_app = (
            open_dialog,
            reset_layout,
            quit_app,
        )

    def render(self, frame: FrameContext) -> None:
        if imgui.begin_menu("File"):
            if imgui.menu_item("Open files or folder…", "Ctrl+O", False)[0]:
                self.open_dialog()
            target(frame, "open")
            if imgui.menu_item("Export active source…", "", False)[0]:
                self.export_dialog()
            if imgui.menu_item("Quit", "", False)[0]:
                self.quit_app()
            imgui.end_menu()
        if imgui.begin_menu("View"):
            if imgui.menu_item("Reset layout", "", False)[0]:
                self.reset_layout()
            imgui.end_menu()
