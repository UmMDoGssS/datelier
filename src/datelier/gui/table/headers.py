"""Prepared physical/interpretation labels with stable native column identities."""

from hashlib import blake2b

from imgui_bundle import imgui

from datelier.application.tabular import TableColumn
from datelier.gui.components.layout import Component, FrameContext
from datelier.gui.components.native import label_text


def label(column: TableColumn, badges: bool) -> str:
    return label_text(column.name + (f" [{column.role.value}]" if badges else ""))


class TableHeaders(Component):
    def __init__(self, columns: tuple[TableColumn, ...], badges: bool) -> None:
        super().__init__("headers")
        self.columns, self.badges = columns, badges

    def render(self, frame: FrameContext) -> None:
        imgui.table_setup_column("Source row", imgui.TableColumnFlags_.width_fixed, 90)
        for column in self.columns:
            identity = int.from_bytes(
                blake2b(column.name.encode(), digest_size=4).digest()
            )
            imgui.table_setup_column(
                label(column, self.badges),
                imgui.TableColumnFlags_.width_fixed,
                150,
                identity,
            )
        imgui.table_setup_scroll_freeze(1, 1)
        imgui.table_next_row(imgui.TableRowFlags_.headers)
        imgui.table_set_column_index(0)
        imgui.table_header("Source row")
        for i, column in enumerate(self.columns, 1):
            imgui.table_set_column_index(i)
            imgui.table_header(label(column, self.badges))
            if imgui.is_item_hovered():
                distinct = column.distinct if column.distinct is not None else "unknown"
                imgui.set_tooltip(
                    f"{column.dtype} · {column.role.value}\n"
                    f"{column.null_count:,} null · "
                    f"{distinct} distinct\n"
                    f"{column.reason}"
                )
