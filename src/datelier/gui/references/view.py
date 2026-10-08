"""Reference settings, explicit ambiguity choices, and prepared cell previews."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.gui.references.textures import PreviewTextures
from datelier.inspection.references.jobs import ReferenceJobs
from datelier.inspection.references.types import ReferenceMapping, ReferenceSettings


class ReferenceView:
    def __init__(self) -> None:
        self.array_columns: frozenset[str] = frozenset()
        self.textures = PreviewTextures()
        self.thumbnails = True
        self._roots = ""
        self._extensions = ""
        self.mapping_path = ""
        self.message = ""
        self._configured: ReferenceSettings | None = None
        self._size, self._cpu, self._gpu = 128, 16, 8
        self.preview_frames = 0

    def controls(self, jobs: ReferenceJobs) -> None:
        if not imgui.collapsing_header("Reference previews"):
            return
        settings = jobs.settings
        imgui.text_wrapped(jobs.message)
        if jobs.busy:
            imgui.text(
                f"Discovery: {jobs.progress.count:,} files found; "
                "previews load on demand."
            )
        _, self.thumbnails = imgui.checkbox("Image thumbnails", self.thumbnails)
        if imgui.button("Retry discovery / previews"):
            jobs.retry()
            self.textures.invalidate()
        imgui.same_line()
        if imgui.button("Abandon discovery"):
            jobs.abandon_index()
        if self._configured != settings:
            self._configured = settings
            self._size = settings.thumbnail_size
            self._cpu, self._gpu = (
                settings.cpu_bytes // 1048576,
                settings.gpu_bytes // 1048576,
            )
            self._roots = "\n".join(settings.roots)
            self._extensions = ",".join(settings.extensions)
        _, self._roots = imgui.input_text_multiline(
            "Roots (one per line; blank = nearby)", self._roots, (0, 55)
        )
        _, self._extensions = imgui.input_text(
            "Extensions (comma-separated)", self._extensions
        )
        _, self._size = imgui.slider_int("Thumbnail pixels", self._size, 32, 512)
        _, self._cpu = imgui.slider_int("CPU cache MiB", self._cpu, 1, 256)
        _, self._gpu = imgui.slider_int("GPU cache MiB", self._gpu, 1, 128)
        if imgui.button("Apply reference settings"):
            try:
                jobs.configure(
                    replace(
                        settings,
                        roots=tuple(
                            r.strip() for r in self._roots.splitlines() if r.strip()
                        ),
                        extensions=tuple(
                            e.strip().lower()
                            for e in self._extensions.split(",")
                            if e.strip()
                        ),
                        thumbnail_size=self._size,
                        cpu_bytes=self._cpu * 1048576,
                        gpu_bytes=self._gpu * 1048576,
                    )
                )
                self.textures.invalidate()
                self.message = ""
            except ValueError as error:
                self.message = str(error)
        imgui.text_wrapped(self.message)
        imgui.text(
            f"Retained CPU {jobs.retained_bytes / 1048576:.2f} MiB / "
            f"GPU {self.textures.retained_bytes / 1048576:.2f} MiB"
        )

    def cell(
        self,
        jobs: ReferenceJobs,
        column: str,
        value: str,
        label: str,
        *,
        extent: float = 56,
    ) -> None:
        if column in self.array_columns:
            imgui.text_unformatted(label)
            return
        resolution, preview = jobs.get(column, value)
        shown = bool(
            preview
            and self.thumbnails
            and self.textures.show(preview, jobs.settings.gpu_bytes, extent)
        )
        if not shown:
            imgui.text_unformatted(label)
        else:
            self.preview_frames += 1
        if imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.text_unformatted(value[:4096])
            if resolution:
                imgui.text_wrapped(resolution.message)
                if resolution.asset:
                    imgui.text_unformatted(str(resolution.asset.path))
            if preview:
                imgui.text_wrapped(preview.description or preview.message)
                if preview.text:
                    imgui.text_unformatted(preview.text)
                if not shown:
                    self.textures.show(preview, jobs.settings.gpu_bytes, 128)
            elif resolution and resolution.asset:
                imgui.text("Preparing preview…")
            imgui.end_tooltip()
        if resolution and (resolution.message or resolution.candidates):
            if imgui.small_button("Choose reference"):
                self.mapping_path = ""
                imgui.open_popup("Reference mapping")
        if imgui.begin_popup("Reference mapping"):
            if resolution:
                imgui.text_wrapped(resolution.message)
                for path in resolution.candidates:
                    if imgui.selectable(str(path), False)[0]:
                        self._map(jobs, column, value, str(path))
                        imgui.close_current_popup()
            _, self.mapping_path = imgui.input_text("Exact file", self.mapping_path)
            if imgui.button("Use file") and self.mapping_path.strip():
                self._map(jobs, column, value, self.mapping_path)
                imgui.close_current_popup()
            imgui.end_popup()

    def _map(self, jobs: ReferenceJobs, column: str, value: str, path: str) -> None:
        settings = jobs.settings
        mappings = tuple(
            m for m in settings.mappings if (m.column, m.value) != (column, value)
        )
        jobs.configure(
            replace(
                settings, mappings=(*mappings, ReferenceMapping(column, value, path))
            )
        )
        self.textures.invalidate()
