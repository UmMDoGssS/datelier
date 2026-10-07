"""Text configuration and a worker-prepared single-record preview."""

from concurrent.futures import Executor
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.gui.text.controls import TextControls, pixel
from datelier.gui.text.profiles import TextProfiles
from datelier.gui.text.training import scope_controls, training_controls
from datelier.inspection.text.jobs import TextJobs

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession


class TextView:
    def __init__(self, executor: Executor | None = None) -> None:
        self.jobs = TextJobs(executor)
        self.controls = TextControls()
        self.shown = 0
        self.profiles = TextProfiles()
        self.profile_pixel = (0.0, 0.0)

    def sync(self, owner: FileSession) -> None:
        dataset = owner.loader.active.dataset if owner.loader.active else None
        self.controls.bind(self.jobs, dataset)
        self.jobs.bind(
            dataset,
            owner.identity,
            owner.references.settings,
            owner.references.index,
            tuple(sorted(owner.selection.row_ids)),
        )
        self.jobs.poll()

    def show(self, owner: FileSession) -> None:
        if not self.controls.columns:
            imgui.text_wrapped("Open a source with a String field to inspect text.")
            return
        import_path = None
        if imgui.collapsing_header("Text settings"):
            import_path = self.controls.show(self.jobs)
        if imgui.collapsing_header("Corpus scope"):
            self.jobs.settings = replace(
                self.jobs.settings, scope=scope_controls(self.jobs.settings.scope)
            )
            _, bins = imgui.input_int(
                "Text length bins", self.jobs.settings.profile_bins
            )
            self.jobs.settings = replace(
                self.jobs.settings, profile_bins=max(1, min(200, bins))
            )
        train = False
        if imgui.collapsing_header("Local tokenizer training"):
            train = training_controls(self.jobs)
        settings = self.jobs.settings
        imgui.text_wrapped(
            f"{settings.column} · {settings.tokens.mode} · {settings.source}"
        )
        # Apply changed controls before dispatch; no source read occurs here.
        self.sync(owner)
        if import_path is not None:
            self.jobs.request_import(import_path)
        if train:
            self.jobs.request_training()
        imgui.text_wrapped(
            f"Corpus scope: {settings.scope.mode} · commands use only this file/view."
        )
        if imgui.button("Calculate corpus profile"):
            self.jobs.request_profile()
        self.profile_pixel = pixel()
        imgui.same_line()
        if imgui.button("Prepare text record"):
            self.jobs.request_document()
        self.controls.prepare_pixel = pixel()
        artifact = settings.tokens.artifact
        if artifact is not None:
            imgui.same_line()
            if imgui.button("Reload saved tokenizer"):
                self.jobs.request_import(Path(artifact.path))
        if self.jobs.busy:
            imgui.same_line()
            if imgui.button("Abandon text preparation"):
                self.jobs.abandon()
                self.jobs.message = (
                    "Result abandoned; executing work may still be running."
                )
            phase, done, total = self.jobs.progress.value
            if phase:
                imgui.text_wrapped(f"{phase} · {done:,}/{total:,} records")
        imgui.text_wrapped(self.jobs.message)
        if artifact and artifact.provenance_path:
            imgui.text_wrapped(f"Training provenance: {artifact.provenance_path}")
        if self.jobs.profile is not None:
            self.profiles.show(self.jobs.profile)
        active = self.jobs.active
        if active is None:
            return
        self.shown += 1
        doc = active.document
        imgui.text_wrapped(
            f"Source row {doc.origin.row_id} · {doc.origin.column} · {doc.status}"
        )
        if doc.diagnostic:
            imgui.text_wrapped(doc.diagnostic)
        imgui.text_wrapped(doc.text[:4096])
        if len(doc.text) > 4096:
            imgui.text("Preview: first 4,096 code points.")
