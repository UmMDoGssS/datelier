"""Shared scalar/nested/preview content over worker-prepared record fields."""

from imgui_bundle import imgui

from datelier.gui.components.base import FrameContext
from datelier.gui.records.base import RecordContent
from datelier.gui.records.textures import TextureCache
from datelier.inspection.references.jobs import ReferenceJobs


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


class GalleryContent(RecordContent):
    def __init__(self, references: ReferenceJobs) -> None:
        super().__init__("preview")
        self.references = references
        self.textures = TextureCache()
        self.height = 80

    def render(self, frame: FrameContext) -> None:
        primary = self.card.primary if self.card else None
        if primary is None:
            return
        if primary.reference:
            resolution, preview = self.references.get(primary.name, primary.reference)
            if preview:
                if not self.textures.draw(
                    preview, self.references.settings.gpu_bytes, 80
                ):
                    imgui.text_wrapped(preview.description or preview.message)
                if preview.text:
                    imgui.text_wrapped(preview.text[:256])
            elif resolution and resolution.message:
                imgui.text_wrapped(resolution.message)
            else:
                imgui.text("Preparing preview…")
        else:
            if imgui.begin_child("excerpt", (0, 65)):
                imgui.text_wrapped(primary.text[:512])
            imgui.end_child()
        if primary.truncated:
            imgui.text_disabled("Truncated preview; open the record for full content.")

    def close(self) -> None:
        self.textures.clear()
        super().close()
