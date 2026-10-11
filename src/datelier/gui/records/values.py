"""Shared scalar/nested/preview content over worker-prepared record fields."""

from imgui_bundle import imgui

from datelier.gui.components.base import FrameContext
from datelier.gui.records.base import RecordContent
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


class GalleryContent(RecordContent):
    def __init__(self, preview: ReferenceFactory) -> None:
        super().__init__("preview")
        self.preview = preview
        self.height = 80

    def render(self, frame: FrameContext) -> None:
        primary = self.card.primary if self.card else None
        if primary is None:
            return
        if primary.reference:
            if imgui.begin_child("reference-preview", (0, 80)):
                self.children = (
                    self.preview(
                        primary.name, primary.reference, primary.text[:256], 80
                    ),
                )
                super().render(frame)
            imgui.end_child()
        else:
            if imgui.begin_child("excerpt", (0, 65)):
                imgui.text_wrapped(primary.text[:512])
            imgui.end_child()
        if primary.truncated:
            imgui.text_disabled("Truncated preview; open the record for full content.")

    def close(self) -> None:
        super().close()
