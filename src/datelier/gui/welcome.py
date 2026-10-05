"""Welcome and failed-import recovery for the active blank file session."""

from dataclasses import dataclass, field
from pathlib import Path

from imgui_bundle import imgui

from datelier.gui.editor_session import EditorSession
from datelier.gui.file_session import FileSession
from datelier.gui.workspace.session_controls import show_recovery
from datelier.io.loading import LoadPhase
from datelier.io.types import ImportFailure
from datelier.workspace.recent import RecentSource


@dataclass
class Welcome:
    open_files_pixel: tuple[float, float] = (0, 0)
    retry_pixel: tuple[float, float] = (0, 0)
    open_folder_pixel: tuple[float, float] = (0, 0)
    recent_pixels: dict[RecentSource, tuple[float, float]] = field(default_factory=dict)
    workspace_requested: bool = False
    recovery_pixel: tuple[float, float] = (0, 0)

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
        self.recovery_pixel = (0, 0)
        if file.recovery is not None:
            imgui.text_wrapped(
                "Recover the saved source to replay this tab's operations."
            )
            self.recovery_pixel = show_recovery(editor, file)
        else:
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
            lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
            self.retry_pixel = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
        if controls.error:
            imgui.text_wrapped(controls.error)
        imgui.text_wrapped(editor.opening.message)
        imgui.text_wrapped(file.loader.status.phase.value)
        if file.loader.status.message and file.recovery is None:
            imgui.text_wrapped(file.loader.status.message)
        if file.loader.status.phase == LoadPhase.LOADING and imgui.button(
            "Abandon load"
        ):
            file.loader.abandon()
        imgui.text_wrapped(
            "CSV/TSV, JSON/JSONL, Parquet and tabular XML are supported."
        )
        if editor.workspace_path:
            imgui.separator()
            imgui.text_wrapped(editor.workspace_jobs.message)
            if imgui.button("Workspace actions…"):
                self.workspace_requested = True
        self.recent_pixels.clear()
        if editor.preferences.value.recent:
            imgui.separator()
            imgui.text("Recent sources")
            for index, source in enumerate(editor.preferences.value.recent):
                path = Path(source.path)
                if imgui.selectable(
                    f"{source.source_kind}: {path.name} — {path.parent}##recent{index}",
                    False,
                )[0]:
                    editor.open_recent(source)
                lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
                self.recent_pixels[source] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
                if imgui.is_item_hovered():
                    imgui.set_tooltip(source.path)
