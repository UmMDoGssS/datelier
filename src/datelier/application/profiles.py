"""Independent profile selection and coalesced preparation."""

from dataclasses import replace
from enum import StrEnum

from datelier.application.columns import ColumnChoice, ProfileSelectionPolicy
from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset
from datelier.inspection.exploration import Explorer
from datelier.inspection.profile_preview import ProfileRequest
from datelier.inspection.table import Inspection
from datelier.inspection.text.list_records import is_text_field


class ProfileFamily(StrEnum):
    COLUMNS = "Columns"
    TEXT = "Text"
    IMAGES = "Images"
    AUDIO = "Audio"


class ProfileController:
    def __init__(self, explorer: Explorer) -> None:
        self.explorer = explorer
        self.choices: tuple[ColumnChoice, ...] = ()
        self.selected: tuple[str, ...] = ()
        self.policy = ProfileSelectionPolicy()
        self.height = 260.0
        self.mode = 0
        self.text = False
        self.can_text = False
        self.text_optional = False
        self.family = ProfileFamily.COLUMNS
        self._dataset_id = None

    def choose(self, names: tuple[str, ...]) -> None:
        self.selected = names

    def restore_selection(
        self, dataset: Dataset, selected: tuple[str, ...] | None
    ) -> None:
        self.selected = selected or ()
        self._dataset_id = dataset.revision.dataset_id if selected is not None else None

    def poll(
        self, inspection: Inspection | None, choices: tuple[ColumnChoice, ...]
    ) -> None:
        self.choices = choices
        if inspection is None:
            return
        available = {choice.name for choice in choices}
        self.selected = tuple(n for n in self.selected if n in available)
        if self._dataset_id != inspection.dataset.revision.dataset_id:
            if not self.selected and choices:
                self.selected = (choices[0].name,)
            self._dataset_id = inspection.dataset.revision.dataset_id
        first = self.selected[0] if self.selected else None
        self.can_text = bool(
            first
            and len(self.selected) == 1
            and is_text_field(inspection.dataset.table.schema[first])
        )
        role = inspection.dataset.role(first).role if first else None
        self.text_optional = self.can_text and role not in (
            ColumnRole.TEXT,
            ColumnRole.EXTERNAL_TEXT,
            ColumnRole.IMAGE,
            ColumnRole.AUDIO,
        )
        families: dict[ColumnRole | None, ProfileFamily] = {
            ColumnRole.TEXT: ProfileFamily.TEXT,
            ColumnRole.EXTERNAL_TEXT: ProfileFamily.TEXT,
            ColumnRole.IMAGE: ProfileFamily.IMAGES,
            ColumnRole.AUDIO: ProfileFamily.AUDIO,
        }
        self.family = families.get(
            role,
            ProfileFamily.TEXT
            if self.text and self.can_text
            else ProfileFamily.COLUMNS,
        )
        if self.family != ProfileFamily.COLUMNS:
            return
        dashboard = self.explorer.active
        if dashboard is None or not self.selected:
            return
        self.explorer.profiles.ensure(
            inspection.dataset,
            ProfileRequest(
                replace(dashboard.settings.comparison, columns=self.selected),
                dashboard.settings.bins,
                dashboard.settings.top_counts,
            ),
        )
