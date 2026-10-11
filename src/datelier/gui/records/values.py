"""Shared scalar/nested/preview content over worker-prepared record fields."""

from imgui_bundle import imgui

from datelier.application.media.images import ArrayGalleryController
from datelier.gui.components.layout import FrameContext
from datelier.gui.components.native import target
from datelier.gui.records.base import RecordContent
from datelier.gui.records.media import TextureCache
from datelier.gui.table.cells import ReferenceFactory


class ValueContent(RecordContent):
    def __init__(self) -> None:
        super().__init__("value")

    def render(self, frame: FrameContext) -> None:
        primary = self.card.primary if self.card else None
        if primary:
            if imgui.begin_child("value", (0, self.height), imgui.ChildFlags_.borders):
                imgui.text_wrapped(primary.text)
            imgui.end_child()
            if primary.truncated:
                imgui.text("Value truncated at 4096 characters.")


class NestedContent(RecordContent):
    def __init__(self) -> None:
        super().__init__("nested")

    def render(self, frame: FrameContext) -> None:
        primary = self.card.primary if self.card else None
        if primary is None or primary.lines is None:
            return
        if imgui.begin_child(
            "nested",
            (0, self.height),
            imgui.ChildFlags_.borders,
            imgui.WindowFlags_.horizontal_scrollbar,
        ):
            clipper = imgui.ListClipper()
            clipper.begin(len(primary.lines))
            while clipper.step():
                for line in primary.lines[clipper.display_start : clipper.display_end]:
                    imgui.text_unformatted(line)
        imgui.end_child()


class ReferenceGallery(RecordContent):
    def __init__(self, preview: ReferenceFactory) -> None:
        super().__init__("reference-preview")
        self.preview = preview

    def render(self, frame: FrameContext) -> None:
        primary = self.card.primary if self.card else None
        if primary is None or primary.reference is None:
            return
        if imgui.begin_child("reference-preview", (0, 80)):
            self.children = (
                self.preview(primary.name, primary.reference, primary.text[:256], 80),
            )
            super().render(frame)
        imgui.end_child()


class ExcerptGallery(RecordContent):
    def __init__(self) -> None:
        super().__init__("excerpt")

    def render(self, frame: FrameContext) -> None:
        primary = self.card.primary if self.card else None
        if primary and imgui.begin_child("excerpt", (0, 65)):
            imgui.text_wrapped(primary.text[:256])
            frame.measure("length", (float(min(256, len(primary.text))), 256))
        if primary:
            imgui.end_child()


class ArrayGallery(RecordContent):
    def __init__(self, model: ArrayGalleryController, textures: TextureCache) -> None:
        super().__init__("array-preview")
        self.model, self.textures = model, textures

    def render(self, frame: FrameContext) -> None:
        if self.card is None:
            return
        preview, message = self.model.get(self.card)
        if imgui.begin_child("array-preview", (0, 80)):
            if preview:
                imgui.text_unformatted(preview.description)
                shown = self.textures.draw_rgba(
                    (self.model.scope, preview.origin),
                    preview.rgba,
                    self.model.references.settings.gpu_bytes,
                    48,
                )
                target(frame, "image")
                frame.measure(
                    "row", (float(preview.origin.row_id), float(preview.step))
                )
                frame.measure("shown", (float(shown), float(preview.retained_bytes)))
                if imgui.is_item_hovered():
                    imgui.set_tooltip(
                        preview.description
                        + f"\nOverview: every {preview.step} original pixels."
                        "\nOpen the record for exact pixel inspection."
                    )
                if preview.step > 1:
                    imgui.same_line()
                    imgui.text_disabled(f"Every {preview.step} pixels")
            else:
                imgui.text_wrapped(message)
        imgui.end_child()


class GalleryContent(RecordContent):
    def __init__(
        self,
        preview: ReferenceFactory,
        arrays: ArrayGalleryController,
        textures: TextureCache,
    ) -> None:
        super().__init__("preview")
        self.arrays = arrays
        self.routes = {
            "Array": ArrayGallery(arrays, textures),
            "Reference": ReferenceGallery(preview),
            "Excerpt": ExcerptGallery(),
        }

    def render(self, frame: FrameContext) -> None:
        primary = self.card.primary if self.card else None
        if primary is None or self.card is None:
            return
        route = (
            "Array"
            if self.arrays.supports(self.card)
            else ("Reference" if primary.reference else "Excerpt")
        )
        content = self.routes[route]
        content.bind_record(self.card)
        self.children = (content,)
        super().render(frame)
        if primary.truncated:
            imgui.text_disabled("Truncated preview; open the record for full content.")

    def close(self) -> None:
        for content in self.routes.values():
            content.close()
        self.card = None
        self.children = ()
