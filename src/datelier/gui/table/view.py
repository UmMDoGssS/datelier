"""Table panel -> controls / virtual rows -> source row -> cells."""

from collections.abc import Callable
from math import ceil

from imgui_bundle import imgui

from datelier.application.media.records import ReferenceController
from datelier.application.tabular import TableColumn, TableController
from datelier.gui.components.layout import Component, Container, FrameContext
from datelier.gui.components.layout.groups import Conditional
from datelier.gui.components.native import help_tip, target
from datelier.gui.references.settings import ReferenceSettings
from datelier.gui.table.cells import ReferenceFactory, TableCell
from datelier.gui.table.headers import TableHeaders
from datelier.gui.table.settings import PresentationSettings
from datelier.inspection.table import PAGE_COLUMNS, PreviewPage


class TableOptions(Container):
    def __init__(
        self, model: TableController, references: ReferenceController | None
    ) -> None:
        super().__init__(
            "options",
            (
                PresentationSettings(model.presentation),
                *(
                    (
                        Conditional(
                            "references",
                            lambda: bool(references.columns),
                            (ReferenceSettings(references),),
                        ),
                    )
                    if references
                    else ()
                ),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        if imgui.button("Cell / reference settings"):
            imgui.open_popup("Table settings")
        target(frame, "open")
        imgui.set_next_window_size((340, 500), imgui.Cond_.appearing)
        if imgui.begin_popup("Table settings"):
            super().render(frame)
            imgui.end_popup()


class TableControls(Container):
    def __init__(
        self, model: TableController, references: ReferenceController | None
    ) -> None:
        super().__init__("controls", (TableOptions(model, references),))
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
        imgui.same_line()
        super().render(frame)
        imgui.text_disabled(
            f"{snapshot.rows:,} rows · source IDs start at 0 · "
            "cells truncate at 256 characters"
        )
        if self.model.selection.message:
            imgui.text_wrapped(self.model.selection.message)
        imgui.same_line()
        help_tip(
            "Click a source row to select; Ctrl-click toggles. "
            "Blue/red means low/high. < / > marks values outside the scale; "
            "= marks a flat scale; (null) is null; ! is nonfinite."
        )


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
        columns: tuple[TableColumn, ...],
        preview: ReferenceFactory | None,
    ) -> None:
        children: tuple[Component, ...]
        offset = row - page.row_start if page else -1
        selected = False
        if (
            page
            and model.snapshot
            and page.revision == model.snapshot.revision
            and 0 <= offset < len(page.rows)
        ):
            selected = page.row_ids[offset] in model.selection.row_ids
            children = (
                SourceRow(model, page.row_ids[offset]),
                *(
                    TableCell(
                        str(i),
                        value,
                        columns[i],
                        page.cells[offset][i] if page.cells else None,
                        model.presentation.settings,
                        selected,
                        page.references[offset][i] if page.references else None,
                        preview,
                    )
                    for i, value in enumerate(page.rows[offset])
                ),
            )
        else:
            children = tuple(TableCell(str(i), "…") for i in range(width + 1))
        super().__init__(str(row), children)
        self.height = height
        self.selected = selected

    def render(self, frame: FrameContext) -> None:
        imgui.push_id(self.key)
        imgui.table_next_row(0, self.height)
        if self.selected:
            imgui.table_set_bg_color(
                imgui.TableBgTarget_.row_bg0,
                imgui.get_color_u32(imgui.ImVec4(0.2, 0.5, 0.8, 0.5)),
            )
        for index, child in enumerate(self.children):
            if imgui.table_set_column_index(index):
                child.render(frame.child(child.key))
        imgui.pop_id()


class TableRows(Container):
    def __init__(
        self,
        model: TableController,
        preview: ReferenceFactory | None,
        references: ReferenceController | None,
    ) -> None:
        super().__init__("rows", ())
        self.model = model
        self.preview, self.references = preview, references
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
        self.children = (
            TableHeaders(columns, self.model.presentation.settings.badges),
        )
        super().render(frame)
        height = (
            ceil(
                (imgui.get_text_line_height() + 2 * imgui.get_style().cell_padding.y)
                / 8
            )
            * 8
        )
        if self.preview and any(c.reference for c in columns):
            height = max(
                height, 64 if self.references and self.references.thumbnails else 48
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
                    columns,
                    self.preview,
                )
                for row in range(clipper.display_start, clipper.display_end)
            )
            super().render(frame)
            self.rendered += len(self.children)
        imgui.end_table()
        if self.model.pages.error:
            imgui.text_wrapped(self.model.pages.error)
            if imgui.button("Retry preview"):
                self.model.pages.retry()


class TableView(Container):
    def __init__(
        self,
        model: TableController,
        preview: ReferenceFactory | None = None,
        references: ReferenceController | None = None,
        metrics: Callable[[], tuple[float, float]] | None = None,
    ) -> None:
        self.metrics = metrics
        super().__init__(
            "table",
            (TableControls(model, references), TableRows(model, preview, references)),
        )

    def render(self, frame: FrameContext) -> None:
        super().render(frame)
        if self.metrics:
            frame.measure("preview-cache", self.metrics())
