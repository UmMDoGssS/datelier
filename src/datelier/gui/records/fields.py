"""Type-neutral record fields share preview styles and explicit detailed tools."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.media.records import RecordController, RecordKind
from datelier.application.tabular import TableController
from datelier.gui.components.layout import Component, Container, FrameContext, Group
from datelier.gui.components.native import target
from datelier.gui.records.base import RecordContent
from datelier.gui.table.cells import TableCell
from datelier.inspection.presentation import CellPresentation
from datelier.inspection.records import RecordCard, RecordField


class FieldText(Component):
    def __init__(self, field: RecordField, gallery: bool) -> None:
        super().__init__("text")
        self.field, self.gallery = field, gallery

    def render(self, frame: FrameContext) -> None:
        field = self.field
        if field.lines is not None and not self.gallery:
            if imgui.begin_child("nested-value", (0, 180)):
                clipper = imgui.ListClipper()
                clipper.begin(len(field.lines))
                while clipper.step():
                    for line in field.lines[
                        clipper.display_start : clipper.display_end
                    ]:
                        imgui.text_unformatted(line)
            imgui.end_child()
            return
        text = field.text[:256] if self.gallery else field.text
        if not self.gallery and len(text) > 256:
            if imgui.begin_child("text-value", (0, 160)):
                imgui.text_wrapped(text)
                target(frame, "value")
            imgui.end_child()
        else:
            imgui.text_wrapped(text)
            target(frame, "value")
        if field.cell and field.cell.note and imgui.is_item_hovered():
            imgui.set_tooltip(field.cell.note)
        if field.truncated or self.gallery and len(field.text) > 256:
            imgui.text_disabled(
                "Preview truncated; use detailed tools for full content."
            )


class FieldValue(Container):
    def __init__(
        self,
        model: RecordController,
        table: TableController,
        card: RecordCard,
        field: RecordField,
        gallery: bool,
        preview: RecordContent,
    ) -> None:
        column = (
            next((c for c in table.snapshot.columns if c.name == field.name), None)
            if table.snapshot
            else None
        )
        self.card = replace(card, primary=field, fields=())
        kind = model.kind(self.card)
        self.preview = preview
        self.show_preview = (
            not field.is_null
            and kind in (RecordKind.IMAGE, RecordKind.AUDIO, RecordKind.ARRAY)
            or field.reference is not None
        )
        # Mapped arbitrary arrays also have a lazy preview route (metadata text
        # for non-image layouts) without resolving them as local file paths.
        content = FieldContent(
            "content",
            (FieldText(field, gallery), *((preview,) if self.show_preview else ())),
            gallery,
        )
        super().__init__(
            "value",
            (
                TableCell(
                    "styled",
                    field.text,
                    column,
                    field.cell or CellPresentation(field.is_null),
                    table.presentation.settings,
                    content=content,
                    shade=kind != RecordKind.IMAGE,
                ),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        self.preview.bind_record(self.card)
        super().render(frame)
        frame.measure("field", (float(self.card.row_id), float(self.show_preview)))


class FieldTools(Component):
    def __init__(
        self, model: RecordController, card: RecordCard, field: RecordField
    ) -> None:
        super().__init__("tools")
        self.model, self.field = model, field
        self.kind = model.kind(replace(card, primary=field))

    def render(self, frame: FrameContext) -> None:
        if (
            self.field.is_null
            or self.kind == RecordKind.VALUE
            or self.field.lines is not None
        ):
            return
        if imgui.small_button(
            "Show full value" if self.kind == RecordKind.NESTED else "Detailed tools"
        ):
            self.model.show_tools(self.field.name)
        target(frame, "open")


class FieldContent(Group):
    def __init__(
        self, key: str, children: tuple[Component, ...], gallery: bool
    ) -> None:
        super().__init__(key, children)
        self.gallery = gallery

    def render(self, frame: FrameContext) -> None:
        if not self.gallery:
            super().render(frame)
            return
        if imgui.begin_child("field-value", (0, 108)):
            super().render(frame)
        imgui.end_child()


class RecordFieldsTable(Container):
    def __init__(
        self,
        model: RecordController,
        table: TableController,
        card: RecordCard,
        preview: RecordContent,
    ) -> None:
        super().__init__("fields", ())
        self.model, self.table, self.card, self.preview = model, table, card, preview

    def render(self, frame: FrameContext) -> None:
        fields = self.model.shown_fields(self.card)
        if not fields:
            imgui.text("Choose columns to show.")
            return
        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.resizable
            | imgui.TableFlags_.scroll_y
        )
        if not imgui.begin_table("fields", 2, flags, (-1, 270)):
            return
        imgui.table_setup_column("Column", imgui.TableColumnFlags_.width_fixed, 150)
        imgui.table_setup_column("Value", imgui.TableColumnFlags_.width_stretch)
        imgui.table_setup_scroll_freeze(0, 1)
        imgui.table_headers_row()
        clipper = imgui.ListClipper()
        clipper.begin(len(fields), 116)
        while clipper.step():
            for index in range(clipper.display_start, clipper.display_end):
                field = fields[index]
                imgui.push_id(index)
                imgui.table_next_row(0, 116)
                imgui.table_set_column_index(0)
                imgui.text_wrapped(field.name)
                imgui.table_set_column_index(1)
                self.children = (
                    FieldValue(
                        self.model, self.table, self.card, field, True, self.preview
                    ),
                )
                super().render(frame.child(field.name))
                imgui.pop_id()
        imgui.end_table()
        frame.measure("columns", (float(len(fields)), 2))


class RecordFieldSection(Container):
    def __init__(
        self,
        model: RecordController,
        table: TableController,
        card: RecordCard,
        field: RecordField,
        preview: RecordContent,
        detailed: Component | None,
    ) -> None:
        self.field = field
        super().__init__(
            field.name,
            (
                FieldValue(model, table, card, field, False, preview),
                *((FieldTools(model, card, field),) if detailed is None else ()),
                *((detailed,) if detailed else ()),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        imgui.push_id(self.key)
        imgui.separator_text(self.field.name)
        target(frame, "title")
        if imgui.begin_table("value", 1, imgui.TableFlags_.sizing_stretch_same):
            imgui.table_next_row()
            imgui.table_next_column()
            super().render(frame)
            imgui.end_table()
        imgui.spacing()
        imgui.pop_id()
