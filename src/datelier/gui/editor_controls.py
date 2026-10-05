"""Application menus and source-bound contextual dialogs."""

from dataclasses import dataclass, field
from pathlib import Path

from imgui_bundle import hello_imgui, imgui

from datelier.gui.editor_session import EditorSession
from datelier.gui.file_session import FileSession
from datelier.io.loading import LoadPhase
from datelier.io.types import ImportFailure, ImportFormat


def item_pixel() -> tuple[float, float]:
    lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
    return (lo.x + hi.x) / 2, (lo.y + hi.y) / 2


@dataclass
class EditorControls:
    dialog: str | None = None
    owner: str | None = None
    _open_requested: bool = False
    menu_pixels: dict[str, tuple[float, float]] = field(default_factory=dict)
    action_pixels: dict[str, tuple[float, float]] = field(default_factory=dict)

    def open_dialog(self, name: str, file: FileSession) -> None:
        if name not in ("Import settings", "Workspace actions"):
            raise ValueError("Unknown editor dialog")
        self.dialog, self.owner, self._open_requested = name, file.identity, True

    def _menu_item(self, label: str, *, enabled: bool = True) -> bool:
        selected = imgui.menu_item(label, "", False, enabled)[0]
        self.menu_pixels[label] = item_pixel()
        return selected

    def show_menu(
        self, editor: EditorSession, params: hello_imgui.RunnerParams
    ) -> None:
        opened = imgui.begin_menu("File")
        self.menu_pixels["File"] = item_pixel()
        if opened:
            if self._menu_item("New Tab"):
                editor.new_tab()
            if self._menu_item("Open Files…"):
                editor.browser.open(editor.active_id)
            if self._menu_item("Open Folder…"):
                editor.browser.open(editor.active_id, folder=True)
            if self._menu_item("Import settings…"):
                self.open_dialog("Import settings", editor.active)
            if self._menu_item("Close Tab"):
                editor.close_tab(editor.active_id)
            imgui.separator()
            if self._menu_item("Workspace actions…"):
                self.open_dialog("Workspace actions", editor.active)
            if imgui.begin_menu(
                "Recent sources", bool(editor.preferences.value.recent)
            ):
                for index, source in enumerate(editor.preferences.value.recent):
                    if imgui.menu_item(
                        f"{source.source_kind}: {source.path}##recent{index}", "", False
                    )[0]:
                        editor.open_recent(source)
                imgui.end_menu()
            imgui.end_menu()
        editor.preferences.show_menu(editor.active, params, sources=editor.source_paths)
        self.menu_pixels.update(editor.preferences.menu_pixels)

    def request_import(self, editor: EditorSession, file: FileSession) -> None:
        controls = file.controls
        try:
            selected = controls.selected_format()
            options = controls.options(selected)
            if file.loader.active is not None:
                file.loader.request(
                    file.loader.active.dataset.source.path, options, format=selected
                )
            elif controls.path.strip():
                editor.opening.request(
                    (Path(controls.path),),
                    file.identity,
                    format=selected,
                    options=options,
                    retry=True,
                )
            else:
                raise ValueError("Enter a file path or use Open Files.")
            controls.error = ""
        except (ValueError, ImportFailure) as error:
            controls.error = str(error)

    def _show_import(self, editor: EditorSession, file: FileSession) -> None:
        controls = file.controls
        if file.loader.active is not None:
            imgui.text_wrapped(f"Source: {file.loader.active.dataset.source.path}")
        else:
            _, controls.path = imgui.input_text("File path", controls.path)
        _, controls.format_index = imgui.combo(
            "Format",
            controls.format_index,
            ["Auto", *[str(value) for value in ImportFormat]],
        )
        try:
            selected = controls.selected_format()
        except ImportFailure:
            selected = None
        controls.show_options(selected)
        imgui.begin_disabled(
            file.loader.status.phase == LoadPhase.LOADING
            or file.editor.busy
            or file.exporter.busy
            or file.workspace.jobs.busy
        )
        label = (
            "Reimport source (resets history)"
            if file.loader.active is not None
            else "Open path / retry import"
        )
        if imgui.button(label):
            self.request_import(editor, file)
        self.action_pixels["Import"] = item_pixel()
        imgui.end_disabled()
        if file.loader.status.phase == LoadPhase.LOADING and imgui.button(
            "Abandon load"
        ):
            file.loader.abandon()
        imgui.text_wrapped(file.loader.status.phase.value)
        if file.loader.status.message:
            imgui.text_wrapped(file.loader.status.message)
        if controls.error:
            imgui.text_wrapped(controls.error)
        if file.loader.active is not None:
            for diagnostic in file.loader.active.imported.diagnostics:
                imgui.text_wrapped(diagnostic)

    def show_dialog(self, editor: EditorSession) -> None:
        if self.dialog is None:
            return
        title = self.dialog
        if self._open_requested:
            imgui.open_popup(title)
            self._open_requested = False
        imgui.set_next_window_size(imgui.ImVec2(620, 520), imgui.Cond_.first_use_ever)
        visible, _ = imgui.begin_popup_modal(title, True)
        if not visible:
            self.dialog = self.owner = None
            return
        file = next(
            (file for file in editor.files if file.identity == self.owner), None
        )
        if file is None:
            imgui.close_current_popup()
            self.dialog = self.owner = None
        else:
            imgui.text_wrapped(f"Tab: {Path(file.controls.path).name or 'Welcome'}")
            if title == "Import settings":
                self._show_import(editor, file)
            else:
                file.workspace.show(file, sources=editor.source_paths)
                self.action_pixels.update(file.workspace.action_pixels)
            imgui.separator()
            if imgui.button("Close dialog"):
                imgui.close_current_popup()
                self.dialog = self.owner = None
            self.action_pixels["Close dialog"] = item_pixel()
        imgui.end_popup()
