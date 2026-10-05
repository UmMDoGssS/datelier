"""Workspace actions with background I/O and explicit changed-source acceptance."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.analysis.types import Algorithm
from datelier.gui_workspace_state import capture_views
from datelier.io.loading import LoadPhase
from datelier.workspace.jobs import WorkspaceJobs

if TYPE_CHECKING:
    from datelier.gui import GuiSession


@dataclass
class WorkspaceControls:
    jobs: WorkspaceJobs = field(default_factory=WorkspaceJobs)
    path: str = ""
    relink_path: str = ""
    overwrite: bool = False
    accept_changed: bool = False
    error: str = ""

    def open(self, session: GuiSession, *, relink: bool = False) -> None:
        if not self.path.strip():
            self.error = "Enter a workspace path."
            return
        session.loader.abandon()
        session.editor.abandon()
        self.jobs.request_restore(
            Path(self.path),
            session.loader.revision,
            relink=Path(self.relink_path)
            if relink and self.relink_path.strip()
            else None,
            accept_changed=self.accept_changed if relink else False,
        )
        self.error = ""

    def save(self, session: GuiSession) -> None:
        pipeline, inspection = session.editor.pipeline, session.loader.active
        if pipeline is None or inspection is None or not self.path.strip():
            self.error = "Open a dataset and enter a workspace path."
            return
        try:
            self.jobs.request_save(
                Path(self.path),
                pipeline,
                inspection.imported,
                tuple(session.analysis.controls.request(a) for a in Algorithm),
                session.plots.settings(),
                capture_views(session),
                overwrite=self.overwrite,
            )
            self.error = ""
        except ValueError as error:
            self.error = str(error)

    def show(self, session: GuiSession) -> None:
        imgui.text_wrapped(self.jobs.message)
        _, self.path = imgui.input_text("Workspace path", self.path)
        imgui.begin_disabled(self.jobs.busy or session.exporter.busy)
        if imgui.button("Open workspace"):
            self.accept_changed = False
            self.open(session)
        imgui.same_line()
        imgui.begin_disabled(
            session.editor.busy or session.loader.status.phase == LoadPhase.LOADING
        )
        if imgui.button("Save workspace"):
            self.save(session)
        imgui.end_disabled()
        _, self.overwrite = imgui.checkbox("Replace existing workspace", self.overwrite)
        imgui.end_disabled()
        if self.jobs.busy and imgui.button("Abandon workspace job"):
            self.jobs.abandon()
        if self.jobs.issue is not None:
            imgui.text_wrapped("Saved source: " + self.jobs.issue.workspace.source.path)
            _, self.relink_path = imgui.input_text(
                "Replacement source", self.relink_path
            )
            _, self.accept_changed = imgui.checkbox(
                "Accept changed source content", self.accept_changed
            )
            if imgui.button("Relink / retry source"):
                self.open(session, relink=True)
        if self.error:
            imgui.text_wrapped(self.error)
        imgui.text_wrapped(
            "Workspaces reference source files. "
            "Run analysis explicitly to recompute results."
        )
