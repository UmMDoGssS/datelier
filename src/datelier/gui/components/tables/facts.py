"""Reusable virtualized facts tables for statistical and provenance results."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.gui.components.layout import Component, FrameContext
from datelier.gui.components.native import number


class FactsTable(Component):
    def __init__(
        self,
        key: str,
        headers: tuple[str, ...],
        rows: Callable[[], tuple[tuple[object, ...], ...]],
        height: float = 160,
        freeze_columns: int = 0,
    ) -> None:
        super().__init__(key)
        self.headers, self.rows, self.height = headers, rows, height
        self.freeze_columns = freeze_columns

    def render(self, frame: FrameContext) -> None:
        rows = self.rows()
        rendered = 0
        if not rows:
            return
        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.scroll_x
            | imgui.TableFlags_.scroll_y
            | imgui.TableFlags_.resizable
            | imgui.TableFlags_.sizing_fixed_fit
        )
        if imgui.begin_table(self.key, len(self.headers), flags, (-1, self.height)):
            for header in self.headers:
                imgui.table_setup_column(
                    header, imgui.TableColumnFlags_.width_fixed, 120
                )
            imgui.table_setup_scroll_freeze(self.freeze_columns, 1)
            imgui.table_headers_row()
            clipper = imgui.ListClipper()
            clipper.begin(len(rows))
            while clipper.step():
                for row in rows[clipper.display_start : clipper.display_end]:
                    rendered += 1
                    imgui.table_next_row()
                    for index, value in enumerate(row):
                        if imgui.table_set_column_index(index):
                            imgui.text_unformatted(number(value))
            imgui.end_table()
        frame.measure("shape", (float(len(rows)), float(len(self.headers))))
        frame.measure("rendered", (float(rendered), float(len(rows))))
