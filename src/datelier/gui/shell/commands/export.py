"""Export captures the chosen source and receives only its export command port."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from imgui_bundle import imgui

from datelier.gui.components.actions import CommandButton, JobFeedback, JobSnapshot
from datelier.gui.components.inputs import BooleanField, ChoiceField, TextField
from datelier.gui.components.layout import Container, FrameContext
from datelier.gui.components.native import window_close_target
from datelier.io.exporting import ExportFormat


@dataclass(frozen=True)
class ExportPort:
    label: str
    request: Callable[[Path, ExportFormat, bool], None]
    status: Callable[[], JobSnapshot]


class ExportDialog(Container):
    def __init__(self, capture: Callable[[], ExportPort | None]) -> None:
        self.capture = capture
        self.binding: ExportPort | None = None
        self.path = ""
        self.format = ExportFormat.CSV
        self.overwrite = False
        self.requested = False
        super().__init__(
            "export",
            (
                TextField(
                    "path",
                    "Destination",
                    lambda: self.path,
                    lambda value: setattr(self, "path", value),
                ),
                ChoiceField(
                    "format",
                    "Format",
                    tuple(ExportFormat),
                    lambda: self.format,
                    lambda value: setattr(self, "format", value),
                ),
                BooleanField(
                    "overwrite",
                    "Replace existing destination",
                    lambda: self.overwrite,
                    lambda value: setattr(self, "overwrite", value),
                ),
                CommandButton(
                    "write",
                    "Export",
                    self.write,
                    lambda: (
                        self.binding is not None
                        and bool(self.path)
                        and not self.binding.status().busy
                    ),
                ),
                JobFeedback(
                    "export-status",
                    lambda: (
                        self.binding.status()
                        if self.binding
                        else JobSnapshot("Open a source before exporting.")
                    ),
                ),
            ),
        )

    def write(self) -> None:
        if self.binding:
            self.binding.request(Path(self.path), self.format, self.overwrite)

    def render(self, frame: FrameContext) -> None:
        if self.requested:
            self.binding = self.capture()
            imgui.open_popup("Export source")
            self.requested = False
        opened, visible = imgui.begin_popup_modal("Export source", True)
        if opened:
            window_close_target(frame)
            imgui.text_wrapped(
                "Source: " + (self.binding.label if self.binding else "No source")
            )
            super().render(frame)
            if imgui.button("Close"):
                self.binding = None
                imgui.close_current_popup()
            imgui.end_popup()
        if visible is False:
            self.binding = None

    def close(self) -> None:
        self.binding = None
        super().close()
