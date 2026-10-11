"""Dialog -> navigation/listing/actions -> fields and polymorphic metadata rows."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

from imgui_bundle import imgui

from datelier.application.browser import (
    DirectoryController,
    DirectoryEntry,
    EntryKind,
)
from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.inputs import TextField
from datelier.gui.components.layout import Component, Container, FrameContext, Group
from datelier.gui.components.layout.groups import Row
from datelier.gui.components.native import label_text, target


class BrowserEntry(Component, ABC):
    def __init__(self, entry: DirectoryEntry) -> None:
        super().__init__(entry.name)
        self.entry = entry

    @abstractmethod
    def selected(self) -> bool: ...

    @abstractmethod
    def choose(self) -> None: ...

    @property
    def label(self) -> str:
        return label_text(self.entry.name)

    def render(self, frame: FrameContext) -> None:
        imgui.push_id(self.entry.name)
        if imgui.selectable(self.label + "###entry", self.selected())[0]:
            self.choose()
        target(frame, "select")
        if imgui.is_item_hovered():
            imgui.set_tooltip(str(self.entry.path) + "\n" + self.entry.description)
        imgui.pop_id()


class FolderEntry(BrowserEntry):
    def __init__(self, entry: DirectoryEntry, browse: Callable[[Path], None]) -> None:
        super().__init__(entry)
        self.browse = browse

    @property
    def label(self) -> str:
        return "▸ " + super().label

    def selected(self) -> bool:
        return False

    def choose(self) -> None:
        self.browse(self.entry.path)


class FileEntry(BrowserEntry):
    def __init__(
        self,
        entry: DirectoryEntry,
        contains: Callable[[Path], bool],
        toggle: Callable[[Path], None],
    ) -> None:
        super().__init__(entry)
        self.contains, self.toggle = contains, toggle

    def selected(self) -> bool:
        return self.contains(self.entry.path)

    def choose(self) -> None:
        self.toggle(self.entry.path)


class BrowserListing(Container):
    def __init__(self, model: DirectoryController) -> None:
        super().__init__("listing", ())
        self.model = model
        self._entries: tuple[DirectoryEntry, ...] = ()
        self._components: dict[DirectoryEntry, BrowserEntry] = {}
        self._factories: dict[EntryKind, Callable[[DirectoryEntry], BrowserEntry]] = {
            EntryKind.FOLDER: lambda entry: FolderEntry(entry, model.request),
            EntryKind.FILE: lambda entry: FileEntry(
                entry, lambda path: path in model.selected, model.toggle
            ),
        }

    def prepare(self) -> None:
        if self.model.entries is not self._entries:
            self._entries = self.model.entries
            self._components = {
                entry: self._factories[entry.kind](entry) for entry in self._entries
            }

    def render(self, frame: FrameContext) -> None:
        imgui.push_id("browser-listing")
        if imgui.begin_child("entries", (0, 240)):
            clipper = imgui.ListClipper()
            clipper.begin(
                len(self.model.shown), imgui.get_text_line_height_with_spacing()
            )
            while clipper.step():
                self.children = tuple(
                    self._components[entry]
                    for entry in self.model.shown[
                        clipper.display_start : clipper.display_end
                    ]
                )
                super().render(frame)
        imgui.end_child()
        imgui.pop_id()


class FileBrowserDialog(Container):
    def __init__(
        self, model: DirectoryController, open_paths: Callable[[tuple[Path, ...]], None]
    ) -> None:
        self.model, self.open_paths = model, open_paths
        self.requested = False
        self._visible = False
        self.listing = BrowserListing(model)
        super().__init__(
            "open",
            (
                Group(
                    "navigation",
                    (
                        TextField(
                            "folder",
                            "Folder",
                            lambda: model.path,
                            lambda value: setattr(model, "path", value),
                        ),
                        Row(
                            "commands",
                            (
                                CommandButton("browse", "Browse", model.browse),
                                CommandButton("parent", "Parent folder", model.parent),
                            ),
                        ),
                        JobFeedback(
                            "status",
                            lambda: JobSnapshot(
                                model.message, model.busy, model.detail
                            ),
                            model.cancel,
                        ),
                    ),
                ),
                Group(
                    "files",
                    (
                        TextField(
                            "search",
                            "Search files",
                            lambda: model.search,
                            lambda value: setattr(model, "search", value),
                        ),
                        self.listing,
                        Row(
                            "commands",
                            (
                                CommandButton(
                                    "select-all",
                                    "Select shown files",
                                    model.select_all,
                                    lambda: bool(model.shown) and not model.busy,
                                ),
                                CommandButton(
                                    "selected",
                                    "Open selected",
                                    lambda: self.submit(model.selected_paths),
                                    lambda: bool(model.selected) and not model.busy,
                                ),
                                CommandButton(
                                    "collection",
                                    "Open media collection",
                                    lambda: self.submit(model.collection_paths),
                                    lambda: (
                                        model.listing is not None and not model.busy
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
                Group(
                    "direct",
                    (
                        TextField(
                            "path",
                            "File or folder path",
                            lambda: model.direct,
                            lambda value: setattr(model, "direct", value),
                        ),
                        Row(
                            "commands",
                            (
                                CommandButton(
                                    "submit",
                                    "Open path",
                                    lambda: self.submit(model.direct_paths),
                                    lambda: bool(model.direct.strip()),
                                ),
                                CommandButton("close", "Close", self.dismiss),
                            ),
                        ),
                    ),
                ),
            ),
        )

    def prepare(self) -> None:
        self.listing.prepare()

    def submit(self, capture: Callable[[], tuple[Path, ...]]) -> None:
        self.open_paths(capture())
        self.dismiss()

    def dismiss(self) -> None:
        self.model.cancel()
        self._visible = False
        imgui.close_current_popup()

    def render(self, frame: FrameContext) -> None:
        if self.requested:
            self.model.request(Path(self.model.path or "."))
            imgui.open_popup("Open files or folder")
            self.requested = False
        imgui.set_next_window_size((640, 520), imgui.Cond_.appearing)
        opened, visible = imgui.begin_popup_modal("Open files or folder", True)
        if not opened:
            if self._visible:
                self.model.cancel()
            self._visible = False
            return
        self._visible = True
        position, size = imgui.get_window_pos(), imgui.get_window_size()
        frame.record(
            "close-window",
            (position.x + size.x - 13, position.y + imgui.get_frame_height() / 2),
        )
        super().render(frame)
        if not visible:
            self.dismiss()
        imgui.end_popup()
