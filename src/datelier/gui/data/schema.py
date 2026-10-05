"""Schema statistics and reversible analysis-role controls."""

from imgui_bundle import imgui

from datelier.core.column_roles import allowed_roles
from datelier.io.loading import DatasetLoader
from datelier.pipeline.editing import DatasetEditor
from datelier.pipeline.operations import SetColumnRole


def show_schema(loader: DatasetLoader, editor: DatasetEditor) -> None:
    inspection = loader.active
    if inspection is None:
        imgui.text("Open a dataset to inspect its schema and missing values.")
        return
    dataset = inspection.dataset
    schema = dataset.table.schema
    imgui.text(f"Shape: ({inspection.row_count:,}, {len(inspection.schema):,})")
    flags = (
        imgui.TableFlags_.borders
        | imgui.TableFlags_.scroll_y
        | imgui.TableFlags_.resizable
        | imgui.TableFlags_.sizing_stretch_prop
    )
    if imgui.begin_table("schema", 5, flags, imgui.ImVec2(-1, -1)):
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
        clipper.begin(len(inspection.schema))
        while clipper.step():
            for index in range(clipper.display_start, clipper.display_end):
                summary = inspection.schema[index]
                info = dataset.role(summary.name)
                imgui.table_next_row()
                for column, text in enumerate(
                    (
                        summary.name,
                        f"{info.nonnull:,}",
                        f"{info.distinct:,}" if info.distinct is not None else "—",
                        summary.dtype,
                    )
                ):
                    imgui.table_set_column_index(column)
                    imgui.text_unformatted(text)
                imgui.table_set_column_index(4)
                options = (None, *allowed_roles(schema[summary.name]))
                labels = [
                    f"Auto: {info.inferred}".replace("Categorical", "Category").replace(
                        "Identifier", "ID"
                    ),
                    *[str(role) for role in options[1:]],
                ]
                imgui.set_next_item_width(-1)
                imgui.begin_disabled(editor.busy)
                changed, choice = imgui.combo(
                    f"##role {summary.name}", options.index(info.override), labels
                )
                imgui.end_disabled()
                if imgui.is_item_hovered():
                    imgui.set_tooltip(f"{info.role}. {info.reason}")
                if changed:
                    editor.request(SetColumnRole(summary.name, options[choice]))
        imgui.end_table()
