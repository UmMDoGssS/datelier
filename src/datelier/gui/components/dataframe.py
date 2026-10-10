"""Virtualized worker-owned result tables shared by all profile families."""

from collections.abc import Callable

import polars as pl
from imgui_bundle import imgui

from datelier.gui.components.base import Component, FrameContext
from datelier.gui.components.native import number


class DataFrameTable(Component):
    def __init__(
        self, key: str, table: Callable[[], pl.DataFrame | None], height: float = 240
    ) -> None:
        super().__init__(key)
        self.table, self.height = table, height

    def render(self, frame: FrameContext) -> None:
        table = self.table()
        if table is None or table.width == 0:
            return
        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.scroll_x
            | imgui.TableFlags_.scroll_y
            | imgui.TableFlags_.resizable
            | imgui.TableFlags_.sizing_fixed_fit
        )
        if imgui.begin_table(self.key, table.width, flags, (-1, self.height)):
            for name in table.columns:
                imgui.table_setup_column(name, imgui.TableColumnFlags_.width_fixed, 130)
            imgui.table_setup_scroll_freeze(0, 1)
            imgui.table_headers_row()
            clipper = imgui.ListClipper()
            clipper.begin(table.height)
            while clipper.step():
                for index in range(clipper.display_start, clipper.display_end):
                    imgui.table_next_row()
                    for value in table.row(index):
                        imgui.table_next_column()
                        text = number(value)
                        imgui.text_unformatted(text[:256])
                        if len(text) > 256 and imgui.is_item_hovered():
                            imgui.set_tooltip(
                                text[:4096]
                                + ("… (preview truncated)" if len(text) > 4096 else "")
                            )
            imgui.end_table()
