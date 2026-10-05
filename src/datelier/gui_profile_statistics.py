"""Scrollable statistics rows beneath the corresponding profile plot."""

from imgui_bundle import imgui

from datelier.gui_profile_colors import profile_color
from datelier.inspection.profiles import ColumnProfile, ProfileKind


def statistics_height(count: int) -> float:
    return imgui.get_text_line_height_with_spacing() * (min(count, 6) + 2) + 36


def _format(value: int | float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,}" if isinstance(value, int) else f"{value:.6g}"


def show_statistics(profiles: tuple[ColumnProfile, ...]) -> None:
    numeric = any(profile.statistics is not None for profile in profiles)
    temporal = bool(profiles) and profiles[0].kind == ProfileKind.TEMPORAL
    mode_heading = (
        "Mode (2 d.p.)"
        if any(p.statistics and p.statistics.rounded_mode for p in profiles)
        else "Mode"
    )
    imgui.separator_text("Statistics")
    headings = (
        (
            "Column",
            "Mean",
            "Std",
            "Min",
            "25%",
            "50%",
            "75%",
            "Max",
            "Non nulls",
            "Uniques",
            "Nulls",
            "NaNs",
            "Non finites",
            mode_heading,
            "Mode count",
        )
        if numeric
        else ("Column", "Non nulls", "Uniques", "Nulls", "Min", "Max")
        if temporal
        else ("Column", "Non nulls", "Uniques", "Nulls", "Mode", "Mode count")
    )
    flags = (
        imgui.TableFlags_.borders
        | imgui.TableFlags_.scroll_x
        | imgui.TableFlags_.scroll_y
        | imgui.TableFlags_.resizable
        | imgui.TableFlags_.sizing_fixed_fit
    )
    table_height = statistics_height(len(profiles)) - 28
    if not imgui.begin_table(
        "Profile statistics", len(headings), flags, (-1, table_height)
    ):
        return
    for index, heading in enumerate(headings):
        imgui.table_setup_column(
            heading,
            imgui.TableColumnFlags_.width_fixed,
            125 if index == 0 else max(75, imgui.calc_text_size(heading).x + 14),
        )
    imgui.table_setup_scroll_freeze(1, 1)
    imgui.table_headers_row()
    if imgui.is_item_hovered():
        imgui.set_tooltip(
            "Finite values only. Std: sample (ddof=1). "
            "Quartiles: linear interpolation. "
            "Mode: floats rounded to 2 decimal places, integers unchanged; "
            "the smallest mode is shown when tied. Non finites includes NaNs."
        )
    clipper = imgui.ListClipper()
    clipper.begin(len(profiles))
    while clipper.step():
        for index in range(clipper.display_start, clipper.display_end):
            profile = profiles[index]
            stats = profile.statistics
            values = (
                (
                    profile.name,
                    stats.mean,
                    stats.std,
                    stats.minimum,
                    stats.q25,
                    stats.median,
                    stats.q75,
                    stats.maximum,
                    stats.nonnull,
                    stats.uniques,
                    stats.nulls,
                    stats.nans,
                    stats.nonfinites,
                    stats.mode,
                    stats.mode_count,
                )
                if stats is not None
                else (
                    profile.name,
                    profile.nonnull_count,
                    profile.unique_count,
                    profile.null_count,
                    profile.minimum or "—",
                    profile.maximum or "—",
                )
                if temporal
                else (
                    profile.name,
                    profile.nonnull_count,
                    profile.unique_count,
                    profile.null_count,
                    profile.distribution.labels[0]
                    if profile.distribution.labels
                    else "—",
                    profile.distribution.counts[0]
                    if profile.distribution.counts
                    else None,
                )
            )
            imgui.table_next_row()
            for column, value in enumerate(values):
                imgui.table_set_column_index(column)
                if column == 0 and stats is not None:
                    imgui.text_colored(profile_color(profile.name), profile.name)
                else:
                    imgui.text_unformatted(
                        value if isinstance(value, str) else _format(value)
                    )
                if stats is not None and column == 13 and imgui.is_item_hovered():
                    imgui.set_tooltip(
                        f"{stats.mode_ties:,} tied modes; smallest shown. "
                        + (
                            "Floats rounded to 2 decimal places."
                            if stats.rounded_mode
                            else ""
                        )
                    )
            if not numeric and imgui.is_item_hovered():
                imgui.set_tooltip(profile.note)
    imgui.end_table()
