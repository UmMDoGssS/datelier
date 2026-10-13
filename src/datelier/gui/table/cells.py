"""Table cells compose prepared text/reference content and display-only styling."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.application.tabular import TableColumn
from datelier.gui import fonts
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
    def __init__(self, text: str, note: str = "") -> None:
        super().__init__("text")
        self.text = text
        self.note = note

    def render(self, frame: FrameContext) -> None:
        imgui.text_unformatted(self.text)
        target(frame, "value")
        if self.note and imgui.is_item_hovered():
            imgui.set_tooltip(self.note)


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
        content: Component | None = None,
        shade: bool = True,
    ) -> None:
        self.style = (
            cell_style(cell, column.bounds if column else None, settings)
            if cell and shade
            else None
        )
        self.selected = selected
        self.cell = cell
        marker = self.style.marker if self.style else ""
        label = f"{marker} {text}" if marker else text
        child = content or (
            preview(column.name, reference, label, 56)
            if preview and column and column.reference and reference is not None
            else TextCell(label, cell.note if cell else "")
        )
        super().__init__(key, (child,))

    def render(self, frame: FrameContext) -> None:
        imgui.push_id(self.key)
        if self.style and self.style.rgba and (not self.selected or self.style.opaque):
            light = imgui.get_style_color_vec4(imgui.Col_.window_bg).x > 0.5
            imgui.table_set_bg_color(
                imgui.TableBgTarget_.cell_bg,
                imgui.get_color_u32(
                    imgui.ImVec4(
                        *self.style.rgba,
                        1 if self.style.opaque else 0.25 if light else 0.35,
                    )
                ),
            )
        foreground = self.style.foreground if self.style else None
        bold = bool(self.style and self.style.bold and fonts.bold_font)
        if foreground:
            imgui.push_style_color(imgui.Col_.text, imgui.ImVec4(*foreground, 1))
        if bold:
            imgui.push_font(fonts.bold_font, imgui.get_font_size())
        super().render(frame)
        if bold:
            imgui.pop_font()
        if foreground:
            imgui.pop_style_color()
        if self.style:
            frame.measure("style", (float(self.style.opaque), float(bold)))
        frame.measure(
            "background",
            (
                float(bool(self.style and self.style.rgba)),
                float(bool(self.style and self.style.opaque)),
            ),
        )
        if self.cell and self.cell.note:
            value = (
                self.cell.text_length
                if self.cell.text_length is not None
                else self.cell.number
            )
            if value is not None:
                frame.measure("mean", (value, float(self.cell.text_length is not None)))
        imgui.pop_id()
