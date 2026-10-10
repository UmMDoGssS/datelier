"""Additional container statistics beneath flattened element profiles."""

from imgui_bundle import imgui

from datelier.gui.profiles.statistics import _format, statistics_height
from datelier.inspection.profiles import ColumnProfile


def list_statistics_height(profiles: tuple[ColumnProfile, ...]) -> float:
    count = sum(
        len(p.list_statistics.dimensions) for p in profiles if p.list_statistics
    )
    shapes = sum(len(p.list_statistics.shapes) for p in profiles if p.list_statistics)
    return statistics_height(count) + statistics_height(shapes) + 85 if count else 0


def show_list_statistics(profiles: tuple[ColumnProfile, ...]) -> None:
    lists = tuple(p for p in profiles if p.list_statistics is not None)
    if not lists:
        return
    imgui.separator_text("List statistics")
    headings = (
        "Column",
        "Depth",
        "Lists",
        "Null lists",
        "Empty lists",
        "Mean length",
        "Min length",
        "Median length",
        "Max length",
    )
    flags = (
        imgui.TableFlags_.borders
        | imgui.TableFlags_.row_bg
        | imgui.TableFlags_.scroll_x
        | imgui.TableFlags_.scroll_y
        | imgui.TableFlags_.resizable
        | imgui.TableFlags_.sizing_fixed_fit
    )
    count = sum(len(p.list_statistics.dimensions) for p in lists if p.list_statistics)
    if imgui.begin_table(
        "List statistics", len(headings), flags, (-1, statistics_height(count) - 28)
    ):
        for heading in headings:
            imgui.table_setup_column(heading)
        imgui.table_setup_scroll_freeze(1, 1)
        imgui.table_headers_row()
        for profile in lists:
            assert profile.list_statistics is not None
            for dimension in profile.list_statistics.dimensions:
                imgui.table_next_row()
                for value in (
                    profile.name,
                    dimension.depth,
                    dimension.containers,
                    dimension.nulls,
                    dimension.empty,
                    dimension.mean,
                    dimension.minimum,
                    dimension.median,
                    dimension.maximum,
                ):
                    imgui.table_next_column()
                    imgui.text_unformatted(
                        value if isinstance(value, str) else _format(value)
                    )
        imgui.end_table()
    for profile in lists:
        stats = profile.list_statistics
        assert stats is not None
        imgui.text_wrapped(
            f"{profile.name}: {stats.elements:,} leaf elements "
            f"({stats.null_elements:,} null) · "
            f"{stats.rectangular:,} rectangular · {stats.ragged:,} ragged · "
            f"{stats.unknown:,} unknown shape."
        )
    imgui.separator_text("List shapes")
    shape_count = sum(len(p.list_statistics.shapes) for p in lists if p.list_statistics)
    if imgui.begin_table(
        "List shapes", 3, flags, (-1, statistics_height(shape_count) - 28)
    ):
        for heading in ("Column", "Shape", "Records"):
            imgui.table_setup_column(heading)
        imgui.table_setup_scroll_freeze(1, 1)
        imgui.table_headers_row()
        for profile in lists:
            stats = profile.list_statistics
            assert stats is not None
            shapes = (
                stats.shapes + (("Other", stats.other_shapes),)
                if stats.other_shapes
                else stats.shapes
            )
            for shape, count in shapes:
                imgui.table_next_row()
                for value in (profile.name, shape, _format(count)):
                    imgui.table_next_column()
                    imgui.text_unformatted(value)
        imgui.end_table()
    imgui.text_wrapped(
        "Lengths include empty lists and exclude null lists. Shapes show up to "
        "12 most frequent; ?/unknown means undetermined inner dimensions."
    )
    if imgui.is_item_hovered():
        imgui.set_tooltip(
            "Depth 1 is the column's outer lists. Later depths pool child lists. "
            "Mean/median exclude null lists and include empty lists. "
            "Shapes exclude null outer lists; ?/unknown denotes undetermined inner "
            "dimensions. Shape counts show the 12 most frequent shapes; Other "
            "counts remaining records. Null/empty containers produce no leaf elements."
        )
