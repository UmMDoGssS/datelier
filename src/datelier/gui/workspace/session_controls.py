"""Whole-session actions and visible recovery for individual source tabs."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from imgui_bundle import hello_imgui, imgui

from datelier.gui.file_session import FileSession
from datelier.io.loading import LoadPhase

if TYPE_CHECKING:
    from datelier.gui.editor_session import EditorSession


def pixel() -> tuple[float, float]:
    lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
    return (lo.x + hi.x) / 2, (lo.y + hi.y) / 2


def show_recovery(editor: EditorSession, file: FileSession) -> tuple[float, float]:
    recovery = file.recovery
    if recovery is None:
        return 0, 0
    imgui.text_wrapped(recovery.message)
    controls = file.workspace
    _, controls.relink_path = imgui.input_text(
        "Replacement source", controls.relink_path
    )
    if recovery.changed:
        _, controls.accept_changed = imgui.checkbox(
            "Accept changed source content", controls.accept_changed
        )
    else:
        controls.accept_changed = False
    imgui.begin_disabled(
        editor.workspace_jobs.session_busy
        or editor.workspace_jobs.recovering(file.identity)
        or file.loader.status.phase == LoadPhase.LOADING
    )
    if imgui.button("Relink / retry source"):
        try:
            editor.recover_source(
                file.identity,
                relink=Path(controls.relink_path)
                if controls.relink_path.strip()
                else None,
                accept_changed=controls.accept_changed,
            )
            controls.error = ""
        except ValueError as error:
            controls.error = str(error)
    target = pixel()
    imgui.end_disabled()
    if editor.workspace_jobs.recovering(file.identity):
        imgui.text("Checking this source…")
    if controls.error:
        imgui.text_wrapped(controls.error)
    return target


@dataclass
class SessionControls:
    overwrite: bool = False
    error: str = ""
    action_pixels: dict[str, tuple[float, float]] = field(default_factory=dict)

    def show(self, editor: EditorSession) -> None:
        jobs = editor.workspace_jobs
        imgui.text_wrapped(jobs.message)
        _, editor.workspace_path = imgui.input_text(
            "Workspace path", editor.workspace_path
        )
        imgui.text_wrapped(
            "Save all tabs, recipes, selections and views. "
            "Open restores editor tabs after checking their sources."
        )
        imgui.begin_disabled(jobs.busy)
        if imgui.button("Open workspace"):
            try:
                if not editor.workspace_path.strip():
                    raise ValueError("Enter a workspace path.")
                editor.open_workspace(Path(editor.workspace_path))
                self.error = ""
            except ValueError as error:
                self.error = str(error)
        self.action_pixels["Open workspace"] = pixel()
        imgui.same_line()
        imgui.begin_disabled(
            any(
                file.loader.status.phase == LoadPhase.LOADING
                or file.editor.busy
                or file.exporter.busy
                for file in editor.files
            )
        )
        if imgui.button("Save workspace"):
            try:
                if not editor.workspace_path.strip():
                    raise ValueError("Enter a workspace path.")
                params = hello_imgui.get_runner_params()
                hidden = tuple(
                    window.label
                    for window in params.docking_params.dockable_windows
                    if not window.is_visible
                )
                editor.save_workspace(
                    Path(editor.workspace_path),
                    layout=imgui.save_ini_settings_to_memory(),
                    hidden=hidden,
                    overwrite=self.overwrite,
                )
                self.error = ""
            except ValueError as error:
                self.error = str(error)
        self.action_pixels["Save workspace"] = pixel()
        imgui.end_disabled()
        _, self.overwrite = imgui.checkbox("Replace existing workspace", self.overwrite)
        imgui.end_disabled()
        if jobs.busy and imgui.button("Abandon workspace jobs"):
            jobs.abandon()
        if self.error:
            imgui.text_wrapped(self.error)
        failures = [file for file in editor.files if file.recovery is not None]
        if failures:
            imgui.separator()
            imgui.text("Sources needing recovery")
            for file in failures:
                if imgui.selectable(
                    f"{Path(file.controls.path).name}##recover{file.identity}",
                    file is editor.active,
                )[0]:
                    editor.activate(file.identity)
            if editor.active.recovery is not None:
                self.action_pixels["Relink / retry source"] = show_recovery(
                    editor, editor.active
                )
        imgui.text_wrapped(
            "Workspaces reference sources. Fitted results are recomputed only "
            "through an explicit analysis command."
        )
