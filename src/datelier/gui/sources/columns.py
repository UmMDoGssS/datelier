"""Column catalog and reversible interpretations, using prepared schema state."""

from collections.abc import Callable

from imgui_bundle import imgui

from datelier.application.tabular import SchemaColumn, SchemaController
from datelier.core.column_roles import ColumnRole
from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.components.native import target


class ColumnDetails(Component):
    def __init__(
        self, column: SchemaColumn, change: Callable[[str, ColumnRole | None], None]
    ) -> None:
        super().__init__(column.name)
        self.column, self.change = column, change

    def render(self, frame: FrameContext) -> None:
        column = self.column
        imgui.push_id(column.name)
        imgui.text_unformatted(column.name)
        imgui.text_disabled(column.dtype)
        imgui.set_next_item_width(-1)
        labels = [
            f"Automatic ({column.role.inferred.value})",
            *(r.value for r in column.options if r is not None),
        ]
        current = (
            column.options.index(column.role.override)
            if column.role.override in column.options
            else 0
        )
        changed, choice = imgui.combo("##interpretation", current, labels)
        target(frame, "role")
        if changed:
            self.change(column.name, column.options[choice])
        if imgui.is_item_hovered():
            imgui.set_tooltip(column.role.reason)
        imgui.separator()
        imgui.pop_id()


class ColumnCatalog(Container):
    def __init__(self, model: SchemaController) -> None:
        super().__init__("columns", ())
        self.model = model
        self.search = ""

    def change(self, name: str, role: ColumnRole | None) -> None:
        if self.model.snapshot:
            self.model.set_role(self.model.snapshot.revision, name, role)

    def render(self, frame: FrameContext) -> None:
        snapshot = self.model.snapshot
        if snapshot is None:
            imgui.text("No source is open.")
            return
        imgui.text(f"{snapshot.rows:,} rows · {len(snapshot.columns):,} columns")
        imgui.set_next_item_width(-1)
        _, self.search = imgui.input_text_with_hint(
            "##search", "Search columns", self.search
        )
        columns = tuple(
            c for c in snapshot.columns if self.search.casefold() in c.name.casefold()
        )
        imgui.begin_disabled(self.model.busy)
        clipper = imgui.ListClipper()
        clipper.begin(
            len(columns),
            imgui.get_frame_height() * 2 + imgui.get_text_line_height() * 2 + 14,
        )
        while clipper.step():
            self.children = tuple(
                ColumnDetails(c, self.change)
                for c in columns[clipper.display_start : clipper.display_end]
            )
            super().render(frame)
        imgui.end_disabled()
        if self.model.error:
            imgui.text_wrapped(self.model.error)
