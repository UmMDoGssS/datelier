"""Table panel -> controls / virtual rows -> source row -> cells."""

from math import ceil

from imgui_bundle import imgui

from datelier.application.table import TableController
from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.components.native import target
from datelier.inspection.table import PAGE_COLUMNS, PreviewPage


class TableControls(Component):
    def __init__(self, model: TableController) -> None:
        super().__init__("controls")
        self.model = model

    def render(self, frame: FrameContext) -> None:
        snapshot = self.model.snapshot
        if snapshot is None:
            return
        if imgui.button("Previous columns"):
            self.model.column_start = max(0, self.model.column_start - PAGE_COLUMNS)
        imgui.same_line()
        if imgui.button("Next columns"):
            if self.model.column_start + PAGE_COLUMNS < len(snapshot.columns):
                self.model.column_start += PAGE_COLUMNS
        imgui.same_line()
        imgui.set_next_item_width(90)
        _, row = imgui.input_int("Row", self.model.target_row)
        self.model.target_row = max(1, min(snapshot.rows, row))
        imgui.same_line()
        if imgui.button("Go"):
            self.model.jump = True
        target(frame, "go")
        imgui.text_disabled(
            f"{snapshot.rows:,} rows · source IDs start at 0 · "
            "cells truncate at 256 characters"
        )


class TableCell(Component):
    def __init__(self, key: str, text: str) -> None:
        super().__init__(key)
        self.text = text

    def render(self, frame: FrameContext) -> None:
        imgui.text_unformatted(self.text)


class SourceRow(Component):
    def __init__(self, model: TableController, row_id: int) -> None:
        super().__init__("source")
        self.model, self.row_id = model, row_id

    def render(self, frame: FrameContext) -> None:
        snapshot = self.model.snapshot
        if snapshot is None:
            return
        selected = self.row_id in self.model.selection.row_ids
        if imgui.selectable(str(self.row_id) + "##row", selected)[0]:
            self.model.selection.choose(
                snapshot.revision, (self.row_id,), toggle=imgui.get_io().key_ctrl
            )
        target(frame, "select")


class TableRow(Container):
    def __init__(
        self,
        model: TableController,
        row: int,
        page: PreviewPage | None,
        width: int,
        height: float,
    ) -> None:
        children: tuple[Component, ...]
        offset = row - page.row_start if page else -1
        if page and 0 <= offset < len(page.rows):
            children = (
                SourceRow(model, page.row_ids[offset]),
                *(
                    TableCell(str(i), value)
                    for i, value in enumerate(page.rows[offset])
                ),
            )
        else:
            children = tuple(TableCell(str(i), "…") for i in range(width + 1))
        super().__init__(str(row), children)
        self.height = height

    def render(self, frame: FrameContext) -> None:
        imgui.push_id(self.key)
        imgui.table_next_row(0, self.height)
        for index, child in enumerate(self.children):
            if imgui.table_set_column_index(index):
                child.render(frame.child(child.key))
        imgui.pop_id()


class TableRows(Container):
    def __init__(self, model: TableController) -> None:
        super().__init__("rows", ())
        self.model = model
        self.rendered = 0

    def render(self, frame: FrameContext) -> None:
        snapshot = self.model.snapshot
        self.rendered = 0
        if snapshot is None:
            imgui.text("Open a source to preview its rows.")
            return
        columns = snapshot.columns[
            self.model.column_start : self.model.column_start + PAGE_COLUMNS
        ]
        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.scroll_y
            | imgui.TableFlags_.scroll_x
            | imgui.TableFlags_.resizable
            | imgui.TableFlags_.sizing_fixed_fit
        )
        if not imgui.begin_table("data", len(columns) + 1, flags, (-1, -1)):
            return
        imgui.table_setup_column("Source row", imgui.TableColumnFlags_.width_fixed, 90)
        for column in columns:
            imgui.table_setup_column(
                column.name, imgui.TableColumnFlags_.width_fixed, 150
            )
        imgui.table_setup_scroll_freeze(1, 1)
        imgui.table_headers_row()
        height = (
            ceil(
                (imgui.get_text_line_height() + 2 * imgui.get_style().cell_padding.y)
                / 8
            )
            * 8
        )
        if self.model.jump:
            imgui.set_scroll_y((self.model.target_row - 1) * height)
            self.model.jump = False
        clipper = imgui.ListClipper()
        clipper.begin(snapshot.rows, height)
        while clipper.step():
            self.children = tuple(
                TableRow(
                    self.model,
                    row,
                    self.model.pages.get(row, self.model.column_start),
                    len(columns),
                    height,
                )
                for row in range(clipper.display_start, clipper.display_end)
            )
            super().render(frame)
            self.rendered += len(self.children)
        imgui.end_table()
        if self.model.pages.error:
            imgui.text_wrapped(self.model.pages.error)


class TableView(Container):
    def __init__(self, model: TableController) -> None:
        super().__init__("table", (TableControls(model), TableRows(model)))
