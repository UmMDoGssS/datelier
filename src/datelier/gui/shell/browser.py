"""Directory dialog -> virtual listing -> prepared metadata entry."""

from collections.abc import Callable
from pathlib import Path

from imgui_bundle import imgui

from datelier.application.browser import DirectoryController
from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.components.native import target


class BrowserEntry(Component):
    def __init__(self, model: DirectoryController, path: Path, folder: bool) -> None:
        super().__init__(str(path))
        self.model, self.path, self.folder = model, path, folder

    def render(self, frame: FrameContext) -> None:
        if self.folder:
            if imgui.selectable("▸ " + self.path.name, False)[0]:
                self.model.request(self.path)
        elif imgui.selectable(self.path.name, self.path in self.model.selected)[0]:
            if self.path in self.model.selected:
                self.model.selected.remove(self.path)
            else:
                self.model.selected.add(self.path)
        target(frame, "select")


class BrowserListing(Container):
    def __init__(self, model: DirectoryController) -> None:
        super().__init__("listing", ())
        self.model = model
        self.search = ""

    def render(self, frame: FrameContext) -> None:
        imgui.set_next_item_width(-1)
        _, self.search = imgui.input_text_with_hint(
            "##search", "Search files", self.search
        )
        listing = self.model.listing
        if imgui.begin_child("entries", (0, 280)) and listing:
            entries = tuple((p, True) for p in listing.folders) + tuple(
                (f.path, False) for f in listing.files
            )
            shown = tuple(
                (p, folder)
                for p, folder in entries
                if self.search.casefold() in p.name.casefold()
            )
            clipper = imgui.ListClipper()
            clipper.begin(len(shown))
            while clipper.step():
                self.children = tuple(
                    BrowserEntry(self.model, p, folder)
                    for p, folder in shown[clipper.display_start : clipper.display_end]
                )
                super().render(frame)
        imgui.end_child()


class FileBrowserDialog(Container):
    def __init__(
        self, model: DirectoryController, open_paths: Callable[[tuple[Path, ...]], None]
    ) -> None:
        super().__init__("open", (BrowserListing(model),))
        self.model, self.open_paths = model, open_paths
        self.requested = False
        self.direct = ""

    def render(self, frame: FrameContext) -> None:
        if self.requested:
            self.model.request(Path(self.model.path))
            imgui.open_popup("Open files or folder")
            self.requested = False
        imgui.set_next_window_size((640, 540), imgui.Cond_.appearing)
        opened, _ = imgui.begin_popup_modal("Open files or folder", True)
        if not opened:
            return
        imgui.set_next_item_width(-100)
        _, self.model.path = imgui.input_text("Folder", self.model.path)
        imgui.same_line()
        if imgui.button("Browse"):
            self.model.request(Path(self.model.path))
        if imgui.button("Parent folder"):
            self.model.request(Path(self.model.path).parent)
        imgui.same_line()
        if imgui.button("Select all") and self.model.listing:
            self.model.selected = {f.path for f in self.model.listing.files}
        imgui.text_wrapped(self.model.message)
        super().render(frame)
        imgui.begin_disabled(not self.model.selected or self.model.busy)
        if imgui.button("Open selected"):
            self.open_paths(tuple(sorted(self.model.selected)))
            imgui.close_current_popup()
        target(frame, "submit")
        imgui.end_disabled()
        imgui.same_line()
        if imgui.button("Open as media collection") and self.model.listing:
            self.open_paths((self.model.listing.directory,))
            imgui.close_current_popup()
        imgui.set_next_item_width(-1)
        _, self.direct = imgui.input_text_with_hint(
            "##direct", "File or folder path", self.direct
        )
        if imgui.button("Open path") and self.direct.strip():
            self.open_paths((Path(self.direct.strip()),))
            imgui.close_current_popup()
        imgui.same_line()
        if imgui.button("Cancel"):
            self.model.cancel()
            imgui.close_current_popup()
        imgui.end_popup()
