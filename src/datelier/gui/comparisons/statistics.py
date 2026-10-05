"""Adjacent, horizontally scrollable source summaries from prepared results."""

from imgui_bundle import imgui

from datelier.gui.profiles.colors import profile_color
from datelier.inspection.comparisons.types import PreparedComparison


def show_statistics(result: PreparedComparison) -> None:
    headings = (
        "Source / column",
        "Rows",
        "Included",
        "Nulls",
        "Nonfinite",
        "Distinct",
        "Mean",
        "Std",
        "Min",
        "25%",
        "Median",
        "75%",
        "Max",
        "Mode",
        "Mode count",
    )
    imgui.separator_text("Statistics")
    flags = (
        imgui.TableFlags_.borders
        | imgui.TableFlags_.scroll_x
        | imgui.TableFlags_.scroll_y
        | imgui.TableFlags_.resizable
        | imgui.TableFlags_.sizing_fixed_fit
    )
    height = imgui.get_text_line_height_with_spacing() * (
        min(len(result.series), 6) + 2
    )
    if not imgui.begin_table("Source statistics", len(headings), flags, (-1, height)):
        return
    for index, title in enumerate(headings):
        imgui.table_setup_column(
            title, imgui.TableColumnFlags_.width_fixed, 180 if index == 0 else 85
        )
    imgui.table_setup_scroll_freeze(1, 1)
    imgui.table_headers_row()
    for s in result.series:
        stats = s.statistics
        values = (
            f"{s.label} / {s.origin.column}",
            s.rows,
            s.included,
            s.nulls,
            s.nonfinite,
            s.distinct,
            stats.mean if stats else None,
            stats.std if stats else None,
            stats.minimum if stats else None,
            stats.q25 if stats else None,
            stats.median if stats else None,
            stats.q75 if stats else None,
            stats.maximum if stats else None,
            stats.mode if stats else s.mode,
            stats.mode_count if stats else s.mode_count,
        )
        imgui.table_next_row()
        for column, value in enumerate(values):
            imgui.table_set_column_index(column)
            text = (
                value
                if isinstance(value, str)
                else "—"
                if value is None
                else f"{value:,}"
                if isinstance(value, int)
                else f"{value:.6g}"
            )
            if column == 0:
                color = (
                    imgui.ImVec4(*s.color)
                    if s.color
                    else profile_color(s.origin.file_id)
                )
                imgui.text_colored(color, text)
            else:
                imgui.text_unformatted(text)
    imgui.end_table()
    if result.series[0].statistics is not None:
        imgui.text_wrapped(
            "Finite values; sample std, linear quartiles. "
            "Float modes: 2 d.p.; smallest tied mode."
        )
