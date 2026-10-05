"""Welcome and failed-import recovery for the active blank file session."""

from dataclasses import dataclass
from pathlib import Path

from imgui_bundle import imgui

from datelier.gui.editor_session import EditorSession
from datelier.gui.file_session import FileSession
from datelier.io.loading import LoadPhase
from datelier.io.types import ImportFailure


@dataclass
class Welcome:
    open_files_pixel: tuple[float, float] = (0, 0)
    open_folder_pixel: tuple[float, float] = (0, 0)

    def show(self, editor: EditorSession, file: FileSession) -> None:
        imgui.text("Welcome to Datelier")
        imgui.text_wrapped("Open local files to inspect them in independent tabs.")
        if imgui.button("Open Files"):
            editor.browser.open(file.identity)
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        self.open_files_pixel = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
        imgui.same_line()
        if imgui.button("Open Folder"):
            editor.browser.open(file.identity, folder=True)
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        self.open_folder_pixel = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
        imgui.separator()
        controls = file.controls
        _, controls.path = imgui.input_text("File path", controls.path)
        if imgui.button("Open path / retry import"):
            try:
                if not controls.path.strip():
                    raise ValueError("Enter a file path or use Open Files.")
                selected = controls.selected_format()
                editor.opening.request(
                    (Path(controls.path),),
                    file.identity,
                    format=selected,
                    options=controls.options(selected),
                    retry=True,
                )
                controls.error = ""
            except (ValueError, ImportFailure) as error:
                controls.error = str(error)
        if controls.error:
            imgui.text_wrapped(controls.error)
        imgui.text_wrapped(editor.opening.message)
        imgui.text_wrapped(file.loader.status.phase.value)
        if file.loader.status.message:
            imgui.text_wrapped(file.loader.status.message)
        if file.loader.status.phase == LoadPhase.LOADING and imgui.button(
            "Abandon load"
        ):
            file.loader.abandon()
        imgui.text_wrapped(
            "CSV/TSV, JSON/JSONL, Parquet and tabular XML are supported."
        )
