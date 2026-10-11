"""Focused original-pixel content; source preparation is an injected command."""

from collections.abc import Callable
from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.images import ImageController
from datelier.gui.annotations.content import AnnotationContent
from datelier.gui.annotations.overlay import AnnotationOverlay
from datelier.gui.components.base import FrameContext
from datelier.gui.components.native import help_tip, target
from datelier.gui.records.base import RecordContent
from datelier.gui.records.pixels import PixelSurface
from datelier.inspection.annotations.association import AssociatedBox
from datelier.inspection.images.viewport import ImageViewport


class ImageContent(RecordContent):
    def __init__(
        self,
        model: ImageController,
        open_rows: Callable[[tuple[int, ...]], None],
        select: Callable[[AssociatedBox], None],
    ) -> None:
        super().__init__("image")
        self.model = model
        self.surface = PixelSurface()
        self.fit = False
        self.children = (
            AnnotationOverlay(
                model.annotation_tools,
                self.surface,
                lambda: model.settings.viewport,
                select,
            ),
            AnnotationContent(model.annotation_tools, open_rows, select),
        )

    def render(self, frame: FrameContext) -> None:
        card = self.card
        if card is None or card.primary is None:
            return
        model = self.model
        model.request_record(card.primary.name, card.position)
        prepared = model.jobs.metadata
        if prepared is None:
            self.surface.clear()
            imgui.text_wrapped(model.jobs.message)
            super().render(frame)
            return
        _, metadata = prepared
        imgui.text(
            f"{metadata.width:,}×{metadata.height:,} · "
            f"{metadata.dtype} · {metadata.mode}"
        )
        viewport = model.settings.viewport
        if imgui.button("1:1 pixels"):
            viewport = ImageViewport(1.0, viewport.left, viewport.top)
        target(frame, "pixels")
        imgui.same_line()
        if imgui.button("Fit image"):
            self.fit = True
        target(frame, "fit-image")
        size = (max(1, imgui.get_content_region_avail().x), max(100, self.height - 60))
        if self.fit:
            viewport = ImageViewport(
                min(32, size[0] / metadata.width, size[1] / metadata.height)
            )
            self.fit = False
        viewport = viewport.clamp(metadata.width, metadata.height, size)
        model.request_window(viewport.window(size))
        viewport = self.surface.draw(
            model.jobs.active, viewport, size, model.settings.gpu_bytes
        )
        frame.measure(
            "gpu", (float(self.surface.retained_bytes), float(self.surface.shown))
        )
        target(frame, "canvas")
        model.settings = replace(
            model.settings,
            viewport=viewport.clamp(metadata.width, metadata.height, size),
        )
        imgui.text_wrapped(model.jobs.message)
        if model.jobs.active and model.jobs.active.window.step > 1:
            imgui.text(
                f"Overview: every {model.jobs.active.window.step} pixels; "
                "zoom for exact values."
            )
        help_tip(
            "Wheel zooms around the pointer; drag pans. "
            "Hover shows original pixel values."
        )
        super().render(frame)

    def close(self) -> None:
        self.surface.clear()
        super().close()
