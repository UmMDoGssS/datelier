"""Virtualized row rendering with bounded, asynchronous column/page preparation."""

from dataclasses import dataclass, field
from math import ceil

from imgui_bundle import imgui

from datelier.inspection.preview import PreviewCache
from datelier.inspection.table import PAGE_COLUMNS, Inspection
from datelier.plotting.selection import LinkedSelection


@dataclass
class TableView:
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
    ) -> None:
        if inspection is None:
            imgui.text("Open a dataset to preview its rows.")
            return
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
        for column in columns:
            imgui.table_setup_column(
                column.name, imgui.TableColumnFlags_.width_fixed, 130
            )
        imgui.table_setup_scroll_freeze(1, 1)
        imgui.table_headers_row()
        # Quantized padding keeps row geometry aligned at million-row scroll
        # offsets, where ImGui's float coordinates lose single-pixel precision.
        content_height = (
            imgui.get_text_line_height() + 2 * imgui.get_style().cell_padding.y
        )
        row_height = ceil(content_height / 8) * 8
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
                            imgui.text_unformatted(value)
                self.rendered_rows += 1
        imgui.end_table()
