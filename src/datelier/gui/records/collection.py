"""Inspect collection -> cards -> header/content/supporting-field components."""

from collections.abc import Callable
from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.records import RecordController, RecordKind
from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.components.native import target
from datelier.gui.components.viewport import ResizableViewport
from datelier.gui.records.base import RecordContent
from datelier.gui.records.values import GalleryContent, NestedContent, ValueContent
from datelier.gui.table.cells import ReferenceFactory
from datelier.inspection.records.types import RecordCard


class RecordHeader(Component):
    def __init__(
        self,
        model: RecordController,
        card: RecordCard,
        slot: int,
        jump: Callable[[int], None],
    ) -> None:
        super().__init__("header")
        self.model, self.card, self.slot, self.jump = model, card, slot, jump

    def render(self, frame: FrameContext) -> None:
        card = self.card
        if imgui.selectable(
            f"Row {card.position + 1:,} · source {card.row_id}",
            card.row_id in self.model.selection.row_ids,
        )[0]:
            self.model.select(card, imgui.get_io().key_ctrl)
            self.jump(card.position)
        target(frame, "select")
        if imgui.is_item_hovered() and imgui.is_mouse_double_clicked(0):
            self.model.focus(self.slot)
        if self.model.settings.gallery:
            imgui.same_line()
            if imgui.small_button("Open"):
                self.model.focus(self.slot)
            target(frame, "open")


class SupportingFields(Component):
    def __init__(self, card: RecordCard, gallery: bool) -> None:
        super().__init__("supporting")
        self.card, self.gallery = card, gallery

    def render(self, frame: FrameContext) -> None:
        if not self.card.fields:
            return
        if imgui.begin_child(
            "fields",
            (0, 65 if self.gallery else 130),
            window_flags=imgui.WindowFlags_.horizontal_scrollbar,
        ):
            clipper = imgui.ListClipper()
            clipper.begin(len(self.card.fields))
            while clipper.step():
                for field in self.card.fields[
                    clipper.display_start : clipper.display_end
                ]:
                    imgui.text_unformatted(f"{field.name}: {field.text}")
                    if imgui.is_item_hovered():
                        imgui.set_tooltip(field.text)
        imgui.end_child()


class RecordBody(Container):
    def __init__(
        self,
        model: RecordController,
        preview: ReferenceFactory,
        content: dict[RecordKind, RecordContent],
        viewport: Callable[[RecordKind, RecordContent], ResizableViewport],
    ) -> None:
        self.model = model
        self.content = {
            RecordKind.VALUE: ValueContent(),
            RecordKind.NESTED: NestedContent(),
            RecordKind.ARRAY: ValueContent(),
            **content,
        }
        self.viewports = {
            kind: viewport(kind, child)
            for kind, child in self.content.items()
            if kind not in (RecordKind.TEXT, RecordKind.ARRAY)
        }
        self.preview = GalleryContent(preview)
        self.card: RecordCard | None = None
        self.gallery = True
        super().__init__("body", ())

    def render(self, frame: FrameContext) -> None:
        if self.card is None:
            return
        if self.gallery:
            self.preview.bind_record(self.card)
            self.children = (self.preview,)
        else:
            kind = self.model.kind(self.card)
            content = self.content[kind]
            content.bind_record(self.card)
            self.children = (
                content
                if kind in (RecordKind.TEXT, RecordKind.ARRAY)
                else self.viewports[kind],
            )
        super().render(frame)

    def close(self) -> None:
        self.card = None
        self.children = ()
        self.preview.close()
        for child in self.content.values():
            child.close()


class RecordCardView(Container):
    def __init__(
        self,
        model: RecordController,
        body: RecordBody,
        card: RecordCard,
        slot: int,
        gallery: bool,
        jump: Callable[[int], None],
    ) -> None:
        super().__init__(
            str(card.row_id),
            (
                RecordHeader(model, card, slot, jump),
                body,
                SupportingFields(card, gallery),
            ),
        )
        self.model = model
        self.body, self.card, self.gallery = body, card, gallery

    def render(self, frame: FrameContext) -> None:
        imgui.push_id(self.key)
        self.body.card, self.body.gallery = (
            self.model.presentation(self.card),
            self.gallery,
        )
        super().render(frame)
        imgui.pop_id()


class RecordCollection(Container):
    def __init__(
        self, model: RecordController, body: RecordBody, jump: Callable[[int], None]
    ) -> None:
        super().__init__("records", ())
        self.model, self.body, self.jump = model, body, jump

    def render(self, frame: FrameContext) -> None:
        model, records = self.model, self.model.jobs.active
        imgui.text_wrapped(model.jobs.message)
        if records is None or not len(records.positions):
            return
        if model.settings.gallery:
            if imgui.begin_child("gallery", (0, 0)):
                clipper = imgui.ListClipper()
                clipper.begin(len(records.positions), 210)
                while clipper.step():
                    for slot in range(clipper.display_start, clipper.display_end):
                        page = model.jobs.get(slot)
                        card = (
                            page.cards[slot - page.start]
                            if page and slot - page.start < len(page.cards)
                            else None
                        )
                        y = imgui.get_cursor_pos_y()
                        if card:
                            self.children = (
                                RecordCardView(
                                    model, self.body, card, slot, True, self.jump
                                ),
                            )
                            super().render(frame)
                        else:
                            imgui.text("Preparing record…")
                        imgui.dummy(
                            (
                                0,
                                max(
                                    0,
                                    y
                                    + 210
                                    - imgui.get_cursor_pos_y()
                                    - imgui.get_style().item_spacing.y,
                                ),
                            )
                        )
            imgui.end_child()
        else:
            focus = min(model.settings.focus, len(records.positions) - 1)
            if imgui.button("Previous record"):
                model.focus(max(0, focus - 1))
            imgui.same_line()
            if imgui.button("Next record"):
                model.focus(min(len(records.positions) - 1, focus + 1))
            target(frame, "next")
            imgui.same_line()
            if imgui.button("Gallery"):
                model.settings = replace(model.settings, gallery=True)
            page = model.jobs.get(focus)
            if page:
                card = page.cards[focus - page.start]
                self.children = (
                    RecordCardView(model, self.body, card, focus, False, self.jump),
                )
                super().render(frame)

    def close(self) -> None:
        self.children = ()
        self.body.close()
