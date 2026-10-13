"""Inspect collection -> cards -> header/content/supporting-field components."""

from collections.abc import Callable
from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.media.records import RecordController, RecordKind
from datelier.application.tabular import TableController
from datelier.gui.components.layout import Component, Container, FrameContext
from datelier.gui.components.layout.viewport import ResizableViewport
from datelier.gui.components.native import target
from datelier.gui.records.base import RecordContent
from datelier.gui.records.fields import RecordFieldSection, RecordFieldsTable
from datelier.inspection.records import RecordCard


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
        width = imgui.get_content_region_avail().x
        if self.model.settings.gallery:
            width -= (
                imgui.calc_text_size("Open").x
                + 2 * imgui.get_style().frame_padding.x
                + imgui.get_style().item_spacing.x
            )
        if imgui.selectable(
            f"Row {card.position + 1:,} · source {card.row_id}",
            card.row_id in self.model.selection.row_ids,
            size=(max(1, width), 0),
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


class RecordBody(Container):
    def __init__(
        self,
        model: RecordController,
        table: TableController,
        preview: RecordContent,
        content: dict[RecordKind, RecordContent],
        viewport: Callable[[RecordKind, RecordContent], ResizableViewport],
    ) -> None:
        self.model = model
        self.table = table
        self.content = content
        self.viewports = {
            kind: viewport(kind, child)
            for kind, child in self.content.items()
            if kind not in (RecordKind.TEXT, RecordKind.ARRAY)
        }
        self.preview = preview
        self.card: RecordCard | None = None
        self.gallery = True
        super().__init__("body", ())

    def render(self, frame: FrameContext) -> None:
        if self.card is None:
            return
        if self.gallery:
            self.children = (
                RecordFieldsTable(self.model, self.table, self.card, self.preview),
            )
        else:
            sections: list[Component] = []
            primary = self.model.presentation(self.card).primary
            for field in self.model.shown_fields(self.card):
                card = replace(self.card, primary=field)
                kind = self.model.kind(card)
                detailed = None
                if (
                    primary
                    and field.name == primary.name
                    and not field.is_null
                    and kind
                    in (
                        RecordKind.TEXT,
                        RecordKind.IMAGE,
                        RecordKind.AUDIO,
                        RecordKind.ARRAY,
                    )
                ):
                    content = self.content[kind]
                    content.bind_record(card)
                    detailed = (
                        content
                        if kind in (RecordKind.TEXT, RecordKind.ARRAY)
                        else self.viewports[kind]
                    )
                sections.append(
                    RecordFieldSection(
                        self.model, self.table, self.card, field, self.preview, detailed
                    )
                )
            self.children = tuple(sections)
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
            ),
        )
        self.model = model
        self.body, self.card, self.gallery = body, card, gallery

    def render(self, frame: FrameContext) -> None:
        imgui.push_id(self.key)
        self.body.card, self.body.gallery = (
            self.card,
            self.gallery,
        )
        if self.gallery:
            if imgui.begin_child("record", (0, 310), imgui.ChildFlags_.borders):
                super().render(frame)
            imgui.end_child()
        else:
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
                clipper.begin(len(records.positions), 326)
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
                                    + 326
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
