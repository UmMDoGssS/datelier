"""Virtualized row rendering with bounded, asynchronous column/page preparation."""

from dataclasses import dataclass, field
from math import ceil

from imgui_bundle import imgui

from datelier.core.column_roles import REFERENCE_ROLES
from datelier.gui.data.presentation import PresentationControls, draw_style
from datelier.gui.references.view import ReferenceView
from datelier.inspection.preview import PreviewCache
from datelier.inspection.references.jobs import ReferenceJobs
from datelier.inspection.table import PAGE_COLUMNS, Inspection
from datelier.plotting.selection import LinkedSelection


@dataclass
class TableView:
    presentation: PresentationControls = field(default_factory=PresentationControls)
    column_start: int = 0
    target_row: int = 1
    jump: bool = False
    rendered_rows: int = 0
    first_visible_row: int = 0
    last_visible_row: int = 0
    prepared_visible_rows: int = 0
    selected_visible_rows: int = 0
    first_row_pixel: tuple[float, float] = (0, 0)
    first_row_id: int | None = None
    row_pixels: dict[int, tuple[float, float]] = field(default_factory=dict)

    def reset(self) -> None:
        self.column_start = 0
        self.target_row = 1
        self.jump = True

    def show(
        self,
        inspection: Inspection | None,
        pages: PreviewCache,
        selection: LinkedSelection | None = None,
        references: ReferenceJobs | None = None,
        reference_view: ReferenceView | None = None,
    ) -> None:
        if inspection is None:
            imgui.text("Open a dataset to preview its rows.")
            return
        if references is not None and reference_view is not None:
            reference_view.controls(references)
        self.presentation.show()
        count = len(inspection.schema)
        if imgui.button("Previous columns"):
            self.column_start = max(0, self.column_start - PAGE_COLUMNS)
        imgui.same_line()
        if imgui.button("Next columns") and self.column_start + PAGE_COLUMNS < count:
            self.column_start += PAGE_COLUMNS
        last = min(count, self.column_start + PAGE_COLUMNS)
        imgui.same_line()
        imgui.text(f"Columns {self.column_start + 1}–{last} of {count}")
        _, self.target_row = imgui.input_int("Go to row", self.target_row)
        imgui.same_line()
        if imgui.button("Go"):
            self.jump = True
        self.target_row = max(1, min(self.target_row, inspection.row_count))
        imgui.text("Source row IDs start at 0. Cells truncate after 256 characters.")
        if selection is not None:
            imgui.text_wrapped(
                "Click a source row to select; Ctrl-click toggles. " + selection.message
            )
        if pages.error:
            imgui.text_wrapped(pages.error)
            if imgui.button("Retry preview"):
                pages.retry()
        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.scroll_y
            | imgui.TableFlags_.scroll_x
            | imgui.TableFlags_.resizable
            | imgui.TableFlags_.sizing_fixed_fit
        )
        columns = inspection.schema[self.column_start : last]
        # The column window also respects Dear ImGui's maximum table-column count.
        if not imgui.begin_table("data", len(columns) + 1, flags, imgui.ImVec2(-1, -1)):
            return
        imgui.table_setup_column("Source row", imgui.TableColumnFlags_.width_fixed, 95)
        headers = []
        for column in columns:
            info = inspection.dataset.role(column.name)
            label = column.name + (
                f" [{info.role}]" if self.presentation.settings.badges else ""
            )
            headers.append(label)
            imgui.table_setup_column(label, imgui.TableColumnFlags_.width_fixed, 160)
        bounds = {b.column: b for b in inspection.bounds}
        imgui.table_setup_scroll_freeze(1, 1)
        imgui.table_next_row(imgui.TableRowFlags_.headers)
        imgui.table_set_column_index(0)
        imgui.table_header("Source row")
        for index, (column, label) in enumerate(zip(columns, headers, strict=True), 1):
            imgui.table_set_column_index(index)
            imgui.table_header(label)
            if imgui.is_item_hovered():
                info = inspection.dataset.role(column.name)
                imgui.set_tooltip(f"{column.dtype}; {info.role}. {info.reason}")
        # Quantized padding keeps row geometry aligned at million-row scroll
        # offsets, where ImGui's float coordinates lose single-pixel precision.
        content_height = (
            imgui.get_text_line_height() + 2 * imgui.get_style().cell_padding.y
        )
        reference_columns = any(
            inspection.dataset.role(c.name).role in REFERENCE_ROLES
            and (reference_view is None or c.name not in reference_view.array_columns)
            for c in columns
        )
        row_height = ceil(content_height / 8) * 8
        if reference_columns and reference_view is not None:
            row_height = max(row_height, 64)
        if self.jump:
            imgui.set_scroll_y((self.target_row - 1) * row_height)
            self.jump = False
        self.rendered_rows = 0
        self.prepared_visible_rows = 0
        self.selected_visible_rows = 0
        self.first_row_id = None
        self.row_pixels.clear()
        clipper = imgui.ListClipper()
        clipper.begin(inspection.row_count, row_height)
        while clipper.step():
            self.first_visible_row = clipper.display_start
            self.last_visible_row = clipper.display_end - 1
            for row in range(clipper.display_start, clipper.display_end):
                page = pages.get(row, self.column_start)
                imgui.table_next_row(0, row_height)
                offset = row - page.row_start if page else 0
                prepared = page is not None and offset < len(page.rows)
                if prepared:
                    assert page is not None
                    values = (str(page.row_ids[offset]), *page.rows[offset])
                    self.prepared_visible_rows += 1
                else:
                    values = ("…",) * (len(columns) + 1)
                row_id = page.row_ids[offset] if prepared and page else None
                selected = selection is not None and row_id in selection.row_ids
                if selected:
                    self.selected_visible_rows += 1
                    imgui.table_set_bg_color(
                        imgui.TableBgTarget_.row_bg0,
                        imgui.get_color_u32(imgui.ImVec4(0.2, 0.5, 0.8, 0.5)),
                    )
                for column, value in enumerate(values):
                    if imgui.table_set_column_index(column):
                        if column == 0 and row_id is not None and selection is not None:
                            if imgui.selectable(f"{value}##row-{row_id}", selected)[0]:
                                selection.choose(
                                    inspection.dataset.revision,
                                    (row_id,),
                                    toggle=imgui.get_io().key_ctrl,
                                )
                            if imgui.is_item_visible():
                                lo, hi = (
                                    imgui.get_item_rect_min(),
                                    imgui.get_item_rect_max(),
                                )
                                pixel = (
                                    (lo.x + hi.x) / 2,
                                    (lo.y + hi.y) / 2,
                                )
                                self.row_pixels[row_id] = pixel
                                if self.first_row_id is None:
                                    self.first_row_pixel = pixel
                                    self.first_row_id = row_id
                        else:
                            if page and prepared and page.cells and column > 0:
                                marker = draw_style(
                                    page.cells[offset][column - 1],
                                    bounds.get(columns[column - 1].name),
                                    self.presentation.settings,
                                    selected,
                                )
                                if marker:
                                    value = f"{marker} {value}"
                            reference = (
                                page.references[offset][column - 1]
                                if page and prepared and page.references and column > 0
                                else None
                            )
                            if reference is not None and references and reference_view:
                                imgui.push_id(f"reference-{row_id}-{column}")
                                reference_view.cell(
                                    references,
                                    columns[column - 1].name,
                                    reference,
                                    value,
                                )
                                imgui.pop_id()
                            else:
                                imgui.text_unformatted(value)
                self.rendered_rows += 1
        imgui.end_table()
