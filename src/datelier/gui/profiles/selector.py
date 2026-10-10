"""Profile-specific policy over the shared column-picker component."""

from datelier.application.columns import ColumnChoice, ProfileSelectionPolicy
from datelier.core.column_roles import LIST_ROLES, ColumnRole
from datelier.gui.components.base import BoundView, FrameContext
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.probe import GuiProbe, ViewScope
from datelier.inspection.profile_selection import ProfileSelection

GROUPS = {
    ColumnRole.NUMERIC: "Numeric",
    ColumnRole.CATEGORY: "Categories",
    ColumnRole.TEMPORAL: "Dates / times",
    ColumnRole.IMAGE: "Image references",
    ColumnRole.OBJECT: "Objects",
    **dict.fromkeys(LIST_ROLES, "Lists / arrays"),
}


class ProfileColumnSelector(BoundView[ProfileSelection]):
    def __init__(self) -> None:
        self.picker = ColumnPicker("Profile columns", ProfileSelectionPolicy())

    def show(self, selection: ProfileSelection) -> None:
        self.bind_view(selection)
        self.render(FrameContext(ViewScope(""), GuiProbe()))

    def draw(self, binding: ProfileSelection, frame: FrameContext) -> None:
        selection = binding
        chosen = selection.columns or ()
        caption = chosen[0] if len(chosen) == 1 else f"Columns ({len(chosen)})"
        selection.columns = self.picker.show(
            tuple(
                ColumnChoice(
                    info.name,
                    GROUPS.get(info.role, "Text / string fields"),
                    info.role == ColumnRole.NUMERIC,
                )
                for info in selection.choices
            ),
            chosen,
            caption=caption,
            bulk_label="All numeric",
            frame=frame,
        )
