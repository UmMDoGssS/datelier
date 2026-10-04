"""Explicit export controls; writes are performed by the background exporter."""

from dataclasses import dataclass
from pathlib import Path

from imgui_bundle import imgui

from datelier.editing import DatasetEditor
from datelier.exporting import DatasetExporter, ExportFormat


@dataclass
class ExportControls:
    path: str = ""
    format: int = 0
    overwrite: bool = False
    error: str = ""

    def show(
        self, editor: DatasetEditor, exporter: DatasetExporter, *, loading: bool
    ) -> None:
        imgui.text_wrapped(exporter.message)
        if exporter.busy:
            imgui.text_wrapped("Export continues if the window closes.")
        imgui.begin_disabled(
            loading or editor.busy or exporter.busy or editor.pipeline is None
        )
        imgui.push_item_width(150)
        try:
            _, self.path = imgui.input_text("Destination", self.path)
            _, self.format = imgui.combo(
                "Export format", self.format, [item.value for item in ExportFormat]
            )
            _, self.overwrite = imgui.checkbox(
                "Replace existing destination", self.overwrite
            )
            imgui.text_wrapped(
                "Source files are always preserved. Exports contain user columns, "
                "without internal row IDs."
            )
            if imgui.button("Export active table"):
                if not self.path.strip():
                    raise ValueError("Enter a destination path")
                assert editor.pipeline is not None
                exporter.request(
                    editor.pipeline.current,
                    Path(self.path),
                    list(ExportFormat)[self.format],
                    overwrite=self.overwrite,
                )
                self.error = ""
        except ValueError as error:
            self.error = str(error)
        finally:
            imgui.pop_item_width()
            imgui.end_disabled()
        if self.error:
            imgui.text_wrapped(self.error)
