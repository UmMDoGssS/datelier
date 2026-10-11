"""Blank file canvas exposes opening commands and prepared recent recipes."""

from collections.abc import Callable
from pathlib import Path

from imgui_bundle import imgui

from datelier.gui.components.actions import CommandButton
from datelier.gui.components.layout import Component, Container, FrameContext
from datelier.gui.components.native import label_text, target
from datelier.workspace.recent import RecentSource


class RecentEntry(Component):
    def __init__(
        self,
        index: int,
        source: RecentSource,
        open_source: Callable[[RecentSource], None],
    ) -> None:
        super().__init__(str(index))
        self.source, self.open_source = source, open_source

    def render(self, frame: FrameContext) -> None:
        caption = label_text(Path(self.source.path).name)
        if imgui.selectable(caption + "###" + self.key, False)[0]:
            self.open_source(self.source)
        target(frame, "open")
        if imgui.is_item_hovered():
            imgui.set_tooltip(self.source.path)
        imgui.text_disabled(str(self.source.format or self.source.source_kind))


class RecentSources(Container):
    def __init__(
        self,
        read: Callable[[], tuple[RecentSource, ...]],
        open_source: Callable[[RecentSource], None],
    ) -> None:
        super().__init__("recent", ())
        self.read, self.open_source = read, open_source

    def render(self, frame: FrameContext) -> None:
        sources = self.read()
        if not sources:
            return
        imgui.separator_text("Recent sources")
        if imgui.begin_child("recent", (0, 280)):
            self.children = tuple(
                RecentEntry(i, source, self.open_source)
                for i, source in enumerate(sources)
            )
            super().render(frame)
        imgui.end_child()


class Welcome(Container):
    def __init__(
        self,
        open_files: Callable[[], None],
        open_workspace: Callable[[], None],
        recent: Callable[[], tuple[RecentSource, ...]],
        open_recent: Callable[[RecentSource], None],
    ) -> None:
        super().__init__(
            "welcome",
            (
                CommandButton("files", "Open files or folder…", open_files),
                CommandButton("workspace", "Open session workspace…", open_workspace),
                RecentSources(recent, open_recent),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        imgui.text("Datelier")
        super().render(frame)
