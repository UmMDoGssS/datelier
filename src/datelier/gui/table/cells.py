"""Table cells compose prepared text/reference content and display-only styling."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.application.tabular import TableColumn
from datelier.gui.components.layout import Component, Container, FrameContext
from datelier.gui.components.native import target
from datelier.inspection.presentation import (
    CellPresentation,
    TablePresentation,
    cell_style,
)

type ReferenceFactory = Callable[[str, str, str, float], Component]
DEFAULT_PRESENTATION = TablePresentation()


class TextCell(Component):
    def __init__(self, text: str) -> None:
        super().__init__("text")
        self.text = text

    def render(self, frame: FrameContext) -> None:
        imgui.text_unformatted(self.text)
        target(frame, "value")


class TableCell(Container):
    def __init__(
        self,
        key: str,
        text: str,
        column: TableColumn | None = None,
        cell: CellPresentation | None = None,
        settings: TablePresentation = DEFAULT_PRESENTATION,
        selected: bool = False,
        reference: str | None = None,
        preview: ReferenceFactory | None = None,
    ) -> None:
        self.style = (
            cell_style(cell, column.bounds if column else None, settings)
            if cell
            else None
        )
        self.selected = selected
        marker = self.style.marker if self.style else ""
        label = f"{marker} {text}" if marker else text
        child = (
            preview(column.name, reference, label, 56)
            if preview and column and column.reference and reference is not None
            else TextCell(label)
        )
        super().__init__(key, (child,))

    def render(self, frame: FrameContext) -> None:
        imgui.push_id(self.key)
        if self.style and self.style.rgba and not self.selected:
            light = imgui.get_style_color_vec4(imgui.Col_.window_bg).x > 0.5
            imgui.table_set_bg_color(
                imgui.TableBgTarget_.cell_bg,
                imgui.get_color_u32(
                    imgui.ImVec4(*self.style.rgba, 0.25 if light else 0.35)
                ),
            )
        super().render(frame)
        imgui.pop_id()
