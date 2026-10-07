"""Virtual scalar image results and linked record navigation."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from datelier.inspection.images.profile_types import ChannelSummary, ImageProfile

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession


def number(value: int | float | None) -> str:
    return (
        "—"
        if value is None
        else f"{value:,}"
        if isinstance(value, int)
        else f"{value:.6g}"
    )


def statistics(label: str, values: tuple[ChannelSummary, ...], height: float) -> None:
    flags = (
        imgui.TableFlags_.borders
        | imgui.TableFlags_.row_bg
        | imgui.TableFlags_.scroll_y
        | imgui.TableFlags_.scroll_x
    )
    if not imgui.begin_table(label, 7, flags, (-1, height)):
        return
    for name in (
        "Field",
        "Finite",
        "Nonfinite",
        "Min",
        "Max",
        "Mean",
        "Population std",
    ):
        imgui.table_setup_column(
            name, imgui.TableColumnFlags_.width_fixed, 130 if name == "Field" else 95
        )
    imgui.table_headers_row()
    clipper = imgui.ListClipper()
    clipper.begin(len(values))
    while clipper.step():
        for row in range(clipper.display_start, clipper.display_end):
            value = values[row]
            imgui.table_next_row()
            for cell in (
                value.key.name if value.key.mode == "Dimensions" else value.key.label,
                number(value.finite),
                number(value.nonfinite),
                number(value.minimum),
                number(value.maximum),
                number(value.mean),
                number(value.stddev),
            ):
                imgui.table_next_column()
                imgui.text_unformatted(cell)
    imgui.end_table()


def record_outcomes(
    profile: ImageProfile,
    owner: FileSession,
    on_select: Callable[[int], None] | None = None,
) -> int:
    flags = (
        imgui.TableFlags_.borders
        | imgui.TableFlags_.row_bg
        | imgui.TableFlags_.scroll_y
        | imgui.TableFlags_.scroll_x
    )
    shown = 0
    names = (
        "row_id",
        "status",
        "width",
        "height",
        "aspect_ratio",
        "mode",
        "profiled_pixels",
        "nonfinite",
        "diagnostic",
    )
    labels = (
        "Source row",
        "Status",
        "Width",
        "Height",
        "Aspect",
        "Mode",
        "Profiled pixels",
        "Nonfinite",
        "Diagnostic",
    )
    if imgui.begin_table("Image record outcomes", len(names), flags, (-1, 270)):
        for name in labels:
            imgui.table_setup_column(
                name,
                imgui.TableColumnFlags_.width_fixed,
                280 if name == "Diagnostic" else 105,
            )
        imgui.table_headers_row()
        clipper = imgui.ListClipper()
        clipper.begin(profile.records.height)
        for_ready = profile.records.columns
        indices = tuple(for_ready.index(name) for name in names)
        row_index = for_ready.index("row_id")
        while clipper.step():
            for row in range(clipper.display_start, clipper.display_end):
                shown += 1
                values = profile.records.row(row)
                imgui.table_next_row()
                imgui.table_next_column()
                row_id = int(values[row_index])
                if imgui.selectable(
                    f"{row_id}##Image profile record", row_id in owner.selection.row_ids
                )[0]:
                    if on_select is not None:
                        on_select(row)
                    else:
                        owner.images.open_profile_record(owner, profile, row)
                for index in indices[1:]:
                    imgui.table_next_column()
                    cell = values[index]
                    imgui.text_unformatted(
                        number(cell)
                        if isinstance(cell, (int, float)) or cell is None
                        else str(cell)
                    )
        imgui.end_table()
    return shown
