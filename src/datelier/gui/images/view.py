"""Full-resolution focused Inspect with worker metadata/windows and saved controls."""

from concurrent.futures import Executor
from dataclasses import replace
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.gui.images.canvas import ImageCanvas
from datelier.inspection.images.jobs import ImageJobs
from datelier.inspection.images.prepare import default_range
from datelier.inspection.images.settings import ImageSettings
from datelier.inspection.images.viewport import ImageViewport
from datelier.io.types import ArrayOptions

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession


class ImageView:
    def __init__(self, executor: Executor | None = None) -> None:
        self.jobs = ImageJobs(executor)
        self.settings = ImageSettings()
        self.canvas = ImageCanvas()
        self.buttons: dict[str, tuple[float, float]] = {}

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

    def show_record(self, owner: FileSession, column: str, position: int) -> None:
        active = owner.loader.active
        if active is None:
            return
        options = active.imported.options
        mapping = options.mapping if isinstance(options, ArrayOptions) else None
        self.jobs.request_record(
            active.dataset, column, position, active.imported.array_catalog, mapping
        )
        if self.jobs.metadata is None:
            if imgui.button("Retry image"):
                self.jobs.abandon()
            imgui.text_wrapped(self.jobs.message)
            return
        _, metadata = self.jobs.metadata
        imgui.text(
            f"{metadata.width:,}×{metadata.height:,} · "
            f"aspect {metadata.aspect_ratio:.3g} · {metadata.dtype}"
        )
        imgui.same_line()
        if imgui.small_button("Retry image"):
            self.jobs.abandon()
            return
        imgui.text(self.jobs.message.split(";")[0])
        names = ["Composite", *metadata.channels]
        if (
            self.settings.display.channel is not None
            and self.settings.display.channel >= len(metadata.channels)
        ):
            self.settings = replace(
                self.settings, display=replace(self.settings.display, channel=None)
            )
        choice = (
            0
            if self.settings.display.channel is None
            else min(len(names) - 1, self.settings.display.channel + 1)
        )
        imgui.set_next_item_width(110)
        changed, choice = imgui.combo("##Image channels", choice, names)
        if changed:
            self.settings = replace(
                self.settings,
                display=replace(
                    self.settings.display, channel=choice - 1 if choice else None
                ),
            )
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
        if imgui.tree_node("Image details and caches"):
            imgui.text_wrapped(metadata.description)
            imgui.text("Wheel to zoom; drag to pan. Hover for original pixel values.")
            if metadata.orientation != 1:
                imgui.text(
                    f"EXIF {metadata.orientation} · "
                    f"source {metadata.source_width}×{metadata.source_height}"
                )
            lo, hi = self.settings.display.value_range or default_range(metadata.dtype)
            imgui.text(f"Display values {lo:g}–{hi:g}")
            for label, name, minimum in (
                ("CPU MiB", "cpu_bytes", 1),
                ("GPU MiB", "gpu_bytes", 1),
                ("Decoded disk MiB", "disk_bytes", 0),
            ):
                imgui.set_next_item_width(120)
                changed, value = imgui.input_int(
                    label, getattr(self.settings, name) // (1024 * 1024)
                )
                if changed and value >= minimum:
                    size_bytes = value * 1024 * 1024
                    if name == "cpu_bytes":
                        self.settings = replace(self.settings, cpu_bytes=size_bytes)
                    elif name == "gpu_bytes":
                        self.settings = replace(self.settings, gpu_bytes=size_bytes)
                    else:
                        self.settings = replace(self.settings, disk_bytes=size_bytes)
            imgui.tree_pop()
        available = imgui.get_content_region_avail()
        size = max(1.0, available.x), max(40.0, min(540.0, available.y - 35))
        if fit:
            viewport = ImageViewport(
                min(32, size[0] / metadata.width, size[1] / metadata.height)
            )
        viewport = viewport.clamp(metadata.width, metadata.height, size)
        self.jobs.request_window(
            viewport.window(size), self.settings.display, owner.arrays.store
        )
        viewport = self.canvas.show(
            self.jobs.active, viewport, size, self.settings.gpu_bytes
        )
        self.settings = replace(
            self.settings,
            viewport=viewport.clamp(metadata.width, metadata.height, size),
        )
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

    def close(self) -> None:
        self.canvas.clear()
        self.jobs.close()
