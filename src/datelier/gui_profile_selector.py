"""A persistent checklist with exclusive categories and multiple numerics."""

from imgui_bundle import imgui

from datelier.column_roles import ColumnRole
from datelier.profile_selection import PROFILE_ROLES, ProfileSelection


def show_selector(selection: ProfileSelection) -> None:
    chosen = selection.columns or ()
    caption = (
        chosen[0]
        if len(chosen) == 1
        else f"{len(chosen)} numeric columns"
        if chosen
        else "Choose columns"
    )
    if imgui.button(caption + "###Profile columns", (-1, 0)):
        imgui.open_popup("Profile column checklist")
    # Popups auto-size every frame. Constrain their extent so a virtualized
    # child with a remaining-space size cannot make the popup shrink repeatedly.
    viewport = imgui.get_main_viewport()
    extent = (min(350, viewport.work_size.x - 20), min(340, viewport.work_size.y - 20))
    imgui.set_next_window_size_constraints(extent, extent)
    if not imgui.begin_popup("Profile column checklist"):
        return
    if imgui.button("All numeric"):
        selection.select_numeric()
    imgui.same_line()
    if imgui.button("Clear"):
        selection.columns = ()
    imgui.same_line()
    if imgui.button("Done"):
        imgui.close_current_popup()
    if imgui.begin_child("Choices", (-1, -1)):
        for role in PROFILE_ROLES:
            choices = tuple(i for i in selection.choices if i.role == role)
            if not choices:
                continue
            imgui.separator_text(
                "Numeric"
                if role == ColumnRole.NUMERIC
                else "Categories"
                if role == ColumnRole.CATEGORY
                else "Dates / times"
            )
            clipper = imgui.ListClipper()
            clipper.begin(len(choices), imgui.get_frame_height_with_spacing())
            while clipper.step():
                for index in range(clipper.display_start, clipper.display_end):
                    name = choices[index].name
                    changed, _ = imgui.checkbox(
                        name + "##Profile choice", name in (selection.columns or ())
                    )
                    if changed:
                        selection.toggle(name)
    imgui.end_child()
    imgui.end_popup()
