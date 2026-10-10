"""Full-resolution focused Inspect with worker metadata/windows and saved controls."""

from concurrent.futures import Executor
from dataclasses import replace
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.gui.annotations.overlay import AnnotationOverlay
from datelier.gui.annotations.overlay_controls import overlay_controls
from datelier.gui.annotations.view import AnnotationView
from datelier.gui.components.viewport import ResizableViewport
from datelier.gui.images.cache_controls import cache_controls
from datelier.gui.images.canvas import ImageCanvas
from datelier.gui.images.heatmap_controls import RecordHeatmapControls
from datelier.gui.images.profile_controls import profile_controls
from datelier.gui.images.profiles import ImageProfiles
from datelier.inspection.annotations.jobs import AnnotationJobs
from datelier.inspection.annotations.profile_jobs import AnnotationProfileJobs
from datelier.inspection.arrays.mapping import ArrayLayout
from datelier.inspection.images.jobs import ImageJobs
from datelier.inspection.images.profile_jobs import ImageProfileJobs
from datelier.inspection.images.profile_types import ImageProfile
from datelier.inspection.images.settings import ImageSettings
from datelier.inspection.images.viewport import ImageViewport
from datelier.inspection.records.types import RecordMode
from datelier.io.types import ArrayOptions

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession


class ImageView:
    def __init__(self, executor: Executor | None = None) -> None:
        self.jobs = ImageJobs(executor)
        self.settings = ImageSettings()
        self.canvas = ImageCanvas()
        self.area = ResizableViewport()
        self.buttons: dict[str, tuple[float, float]] = {}
        self.profile_jobs = ImageProfileJobs(executor)
        self.profiles = ImageProfiles()
        self.profile_pixel = (0.0, 0.0)
        self.heatmap = RecordHeatmapControls()
        self.annotations = AnnotationJobs(executor)
        self.annotation_controls = AnnotationView()
        self.annotation_profiles = AnnotationProfileJobs(executor)
        self.overlay = AnnotationOverlay()

    def sync(self, owner: FileSession) -> None:
        active = owner.loader.active
        self.jobs.sync(
            owner.identity,
            owner.view_name,
            active.dataset.revision if active else None,
            owner.references.settings,
            owner.references.index,
        )
        self.jobs.cpu_bytes = min(self.settings.cpu_bytes, self.settings.gpu_bytes)
        self.jobs.set_retention(self.settings.disk_bytes)
        self.jobs.poll()
        if (
            self.jobs.metadata is None
            or self.canvas.retained_bytes > self.settings.gpu_bytes
        ):
            self.canvas.clear()
        self.profile_jobs.settings = self.settings.profile
        options = active.imported.options if active else None
        catalog = active.imported.array_catalog if active else None
        mapping = (
            options.mapping_for(catalog, self.settings.profile.column)
            if isinstance(options, ArrayOptions)
            else None
        )
        self.profile_jobs.bind(
            active.dataset if active else None,
            owner.identity,
            owner.view_name,
            owner.references.settings,
            owner.references.index,
            tuple(sorted(owner.selection.row_ids)),
            owner.arrays.store,
            active.imported.array_catalog if active else None,
            mapping,
        )
        self.profile_jobs.poll()
        self.annotations.settings = self.settings.annotations
        self.annotations.bind(
            active.dataset if active else None,
            owner.identity,
            owner.view_name,
            owner.references.settings,
            owner.references.index,
            active.imported.array_catalog if active else None,
            options.mapping_for(catalog, owner.inspect.settings.primary)
            if isinstance(options, ArrayOptions)
            else None,
        )
        self.annotations.poll()
        if self.annotations.active is not None:
            self.settings = replace(
                self.settings, annotations=self.annotations.settings
            )
        self.overlay.bind(self.annotations.active)
        self.annotation_profiles.bins = self.settings.annotation_view.bins
        self.annotation_profiles.bind(self.annotations.active)
        self.annotation_profiles.poll()

    def show_mapped_profile(self, owner: FileSession) -> bool:
        active = owner.loader.active
        options = active.imported.options if active else None
        if (
            not isinstance(options, ArrayOptions)
            or options.mapping is None
            or options.mapping.layout != ArrayLayout.IMAGE
        ):
            return False
        if imgui.button(
            "Table columns"
            if self.settings.profile_payload
            else "Profile mapped images"
        ):
            self.settings = replace(
                self.settings, profile_payload=not self.settings.profile_payload
            )
        if self.settings.profile_payload:
            self.show_profile(owner, options.mapping.member)
            return True
        return False

    def show_profile(self, owner: FileSession, column: str) -> None:
        settings = replace(self.settings.profile, column=column)
        self.settings = replace(self.settings, profile=profile_controls(settings))
        self.sync(owner)
        if imgui.button("Prepare image profile"):
            try:
                self.profile_jobs.request()
            except ValueError as error:
                self.profile_jobs.message = str(error)
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        self.profile_pixel = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
        if self.profile_jobs.busy:
            imgui.same_line()
            if imgui.button("Abandon image profiling"):
                self.profile_jobs.abandon()
                self.profile_jobs.message = (
                    "Profiling abandoned; any executing decode is winding down."
                )
            phase, done, total = self.profile_jobs.progress.value
            imgui.text(f"{phase} · {done:,}/{total:,}")
        if self.profile_jobs.active is None:
            imgui.text_wrapped(self.profile_jobs.message)
        if self.profile_jobs.active is not None:
            view = self.profiles.show(
                self.profile_jobs.active, self.settings.profile_view, owner
            )
            self.settings = replace(self.settings, profile_view=view)

    def open_profile_record(
        self, owner: FileSession, profile: ImageProfile, row: int
    ) -> None:
        active = owner.loader.active
        if active is None or (profile.file_id, profile.view_name, profile.revision) != (
            owner.identity,
            owner.view_name,
            active.dataset.revision,
        ):
            return
        row_id, position = (
            int(profile.records["row_id"][row]),
            int(profile.records["position"][row]),
        )
        owner.selection.choose(profile.revision, (row_id,))
        owner.table.target_row, owner.table.jump = position + 1, True
        owner.inspect.settings = replace(
            owner.inspect.settings,
            mode=RecordMode.SELECTION,
            gallery=False,
            focus=0,
            primary=profile.settings.column
            if profile.mapping is None
            else owner.inspect.settings.primary,
        )
        owner.exploration.tab = "Inspect"

    def show_record(self, owner: FileSession, column: str, position: int) -> None:
        active = owner.loader.active
        if active is None:
            return
        options = active.imported.options
        mapping = (
            options.mapping_for(active.imported.array_catalog, column)
            if isinstance(options, ArrayOptions)
            else None
        )
        self.jobs.request_record(
            active.dataset, column, position, active.imported.array_catalog, mapping
        )
        if self.jobs.metadata is None:
            if imgui.button("Retry image"):
                self.jobs.abandon()
            imgui.text_wrapped(self.jobs.message)
            return
        locator, metadata = self.jobs.metadata
        imgui.text(
            f"{metadata.width:,}×{metadata.height:,} · "
            f"aspect {metadata.aspect_ratio:.3g} · {metadata.dtype}"
        )
        imgui.same_line()
        if imgui.small_button("Retry image"):
            self.jobs.abandon()
            return
        imgui.text(self.jobs.message.split(";")[0])
        self.settings = replace(
            self.settings,
            annotation_view=replace(
                self.settings.annotation_view,
                overlay=overlay_controls(
                    self.settings.annotation_view.overlay, self.annotations.active
                ),
            ),
        )
        if metadata.mode == "Numeric":
            self.settings = replace(
                self.settings,
                display=self.heatmap.show(
                    locator, metadata, self.settings.display, self.jobs.active
                ),
            )
        else:
            self._channels(metadata.channels)
        viewport = self.settings.viewport
        imgui.same_line()
        if imgui.button("1:1 pixels"):
            viewport = ImageViewport(1.0, viewport.left, viewport.top)
        self._capture("1:1 pixels")
        imgui.same_line()
        fit = imgui.button("Fit image")
        self._capture("Fit image")
        imgui.same_line()
        imgui.text(f"{viewport.zoom * 100:.1f}%")
        self.settings = cache_controls(self.settings, metadata)

        def draw(height: float, auto_fit: bool) -> bool:
            nonlocal viewport
            size = max(1.0, imgui.get_content_region_avail().x), height
            if fit:
                viewport = ImageViewport(
                    min(32, size[0] / metadata.width, size[1] / metadata.height)
                )
            viewport = viewport.clamp(metadata.width, metadata.height, size)
            self.jobs.request_window(
                viewport.window(size), self.settings.display, owner.arrays.store
            )
            original_viewport = viewport
            viewport = self.canvas.show(
                self.jobs.active, viewport, size, self.settings.gpu_bytes
            )
            self.overlay.show(
                self.canvas,
                original_viewport,
                self.settings.annotation_view.overlay,
                owner,
            )
            self.settings = replace(
                self.settings,
                viewport=viewport.clamp(metadata.width, metadata.height, size),
            )
            return True

        self.area.show_content("Image", locator, draw, minimum_height=100)
        if self.jobs.active is not None:
            if self.jobs.active.window.step > 1:
                imgui.text(
                    f"Overview: every {self.jobs.active.window.step} pixels. "
                    "Zoom to inspect original pixels."
                )
            if self.jobs.active.nonfinite:
                imgui.text(
                    f"{self.jobs.active.nonfinite:,} nonfinite values marked magenta"
                )

    def _capture(self, label: str) -> None:
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        self.buttons[label] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)

    def _channels(self, channels: tuple[str, ...]) -> None:
        names = ["Composite", *channels]
        display = self.settings.display
        if display.channel is not None and display.channel >= len(channels):
            display = replace(display, channel=None)
        choice = 0 if display.channel is None else display.channel + 1
        imgui.set_next_item_width(110)
        changed, choice = imgui.combo("##Image channels", choice, names)
        if changed:
            display = replace(display, channel=choice - 1 if choice else None)
        self.settings = replace(self.settings, display=display)

    def close(self) -> None:
        self.canvas.clear()
        self.overlay.bind(None)
        self.jobs.close()
        self.profile_jobs.close()
        self.annotations.close()
        self.annotation_profiles.close()
