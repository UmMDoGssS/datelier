"""Workspace dialog with narrow save/open/cancel command dependencies."""

from collections.abc import Callable
from pathlib import Path

from imgui_bundle import imgui

from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.inputs import BooleanField, TextField
from datelier.gui.components.layout import Container, FrameContext


class WorkspaceDialog(Container):
    def __init__(
        self,
        save: Callable[[Path, bool], None],
        open_workspace: Callable[[Path], None],
        status: Callable[[], JobSnapshot],
        cancel: Callable[[], None],
    ) -> None:
        self.path, self.overwrite, self.requested = "", False, False
        super().__init__(
            "workspace",
            (
                TextField(
                    "path",
                    "Workspace path",
                    lambda: self.path,
                    lambda value: setattr(self, "path", value),
                ),
                BooleanField(
                    "overwrite",
                    "Replace existing workspace",
                    lambda: self.overwrite,
                    lambda value: setattr(self, "overwrite", value),
                ),
                CommandButton(
                    "save",
                    "Save all tabs",
                    lambda: save(Path(self.path), self.overwrite),
                    lambda: bool(self.path) and not status().busy,
                ),
                CommandButton(
                    "open",
                    "Open workspace",
                    lambda: open_workspace(Path(self.path)),
                    lambda: bool(self.path) and not status().busy,
                ),
                JobFeedback("status", status, cancel),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        if self.requested:
            imgui.open_popup("Session workspace")
            self.requested = False
        imgui.set_next_window_size((550, 300), imgui.Cond_.appearing)
        opened, _ = imgui.begin_popup_modal("Session workspace", True)
        if opened:
            super().render(frame)
            if imgui.button("Close"):
                imgui.close_current_popup()
            imgui.end_popup()
