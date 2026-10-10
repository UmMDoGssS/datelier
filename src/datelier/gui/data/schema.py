"""Column metadata components; preparation and editing belong to the controller."""

from imgui_bundle import imgui

from datelier.application.schema import SchemaColumn, SchemaController, SchemaSnapshot
from datelier.gui.components.base import Component, FrameContext, Panel


class SchemaSummary(Component):
    def __init__(self, controller: SchemaController) -> None:
        self.controller = controller

    def render(self, frame: FrameContext) -> None:
        snapshot = self.controller.snapshot
        if snapshot is None:
            imgui.text("Open a dataset to inspect its schema and missing values.")
        else:
            imgui.text(f"Shape: ({snapshot.rows:,}, {len(snapshot.columns):,})")
        if self.controller.error:
            imgui.text_wrapped(self.controller.error)


class SchemaRow(Component):
    def __init__(self, controller: SchemaController, column: SchemaColumn) -> None:
        self.controller = controller
        self.column = column

    def render(self, frame: FrameContext) -> None:
        column, info = self.column, self.column.role
        imgui.table_next_row()
        for index, text in enumerate(
            (
                column.name,
                f"{info.nonnull:,}",
                f"{info.distinct:,}" if info.distinct is not None else "—",
                column.dtype,
            )
        ):
            imgui.table_set_column_index(index)
            imgui.text_unformatted(text)
        imgui.table_set_column_index(4)
        self.role_control(frame)

    def compact(self, frame: FrameContext) -> None:
        column, info = self.column, self.column.role
        imgui.text_unformatted(column.name)
        snapshot = self.controller.snapshot
        missing = snapshot.rows - info.nonnull if snapshot else 0
        imgui.text_disabled(f"{column.dtype} · {missing:,} missing")
        if imgui.is_item_hovered():
            imgui.set_tooltip(
                f"{info.nonnull:,} nonnull · {info.distinct:,} distinct"
                if info.distinct is not None
                else f"{info.nonnull:,} nonnull"
            )
        self.role_control(frame)
        imgui.separator()

    def role_control(self, frame: FrameContext) -> None:
        column, info = self.column, self.column.role
        labels = [
            f"Auto: {info.inferred}".replace("Categorical", "Category").replace(
                "Identifier", "ID"
            ),
            *map(str, column.options[1:]),
        ]
        imgui.set_next_item_width(-1)
        imgui.begin_disabled(self.controller.busy)
        changed, choice = imgui.combo(
            f"##role {column.name}", column.options.index(info.override), labels
        )
        imgui.end_disabled()
        low, high = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        frame.record(column.name, ((low.x + high.x) / 2, (low.y + high.y) / 2))
        if imgui.is_item_hovered():
            imgui.set_tooltip(f"{info.role}. {info.reason}")
        if changed and frame.scope.revision is not None:
            self.controller.set_role(
                frame.scope.revision, column.name, column.options[choice]
            )


class SchemaTable(Component):
    def __init__(self, controller: SchemaController) -> None:
        self.controller = controller
        self._snapshot: SchemaSnapshot | None = None
        self._rows: tuple[SchemaRow, ...] = ()

    def render(self, frame: FrameContext) -> None:
        snapshot = self.controller.snapshot
        if snapshot is None:
            self._snapshot, self._rows = None, ()
            return
        if snapshot is not self._snapshot:
            self._snapshot = snapshot
            self._rows = tuple(
                SchemaRow(self.controller, column) for column in snapshot.columns
            )
        if imgui.get_content_region_avail().x < 450:
            if imgui.begin_child("Column catalog", (-1, -1)):
                row_height = (
                    imgui.get_text_line_height_with_spacing() * 2
                    + imgui.get_frame_height_with_spacing()
                    + 5
                )
                clipper = imgui.ListClipper()
                clipper.begin(len(self._rows), row_height)
                while clipper.step():
                    for index in range(clipper.display_start, clipper.display_end):
                        self._rows[index].compact(frame.child("roles"))
            imgui.end_child()
            return
        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.scroll_y
            | imgui.TableFlags_.resizable
            | imgui.TableFlags_.sizing_stretch_prop
        )
        if not imgui.begin_table("schema", 5, flags, imgui.ImVec2(-1, -1)):
            return
        for name, weight in (
            ("Column", 1.0),
            ("Non nulls", 1.15),
            ("Uniques", 0.85),
            ("Type", 0.7),
            ("Interpretation", 1.9),
        ):
            imgui.table_setup_column(name, init_width_or_weight=weight)
        imgui.table_setup_scroll_freeze(0, 1)
        imgui.table_headers_row()
        clipper = imgui.ListClipper()
        clipper.begin(len(self._rows))
        while clipper.step():
            for index in range(clipper.display_start, clipper.display_end):
                self._rows[index].render(frame.child("roles"))
        imgui.end_table()


class SchemaPanel(Panel):
    def __init__(self, controller: SchemaController) -> None:
        super().__init__("schema", (SchemaSummary(controller), SchemaTable(controller)))
