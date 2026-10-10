"""Independent profile selection and coalesced preparation."""

from dataclasses import replace

from datelier.application.columns import ColumnChoice, ProfileSelectionPolicy
from datelier.inspection.exploration import Explorer
from datelier.inspection.profile_preview import ProfileRequest
from datelier.inspection.table import Inspection


class ProfileController:
    def __init__(self, explorer: Explorer) -> None:
        self.explorer = explorer
        self.choices: tuple[ColumnChoice, ...] = ()
        self.selected: tuple[str, ...] = ()
        self.policy = ProfileSelectionPolicy()
        self.height = 260.0
        self.mode = 0
        self.text = False

    def choose(self, names: tuple[str, ...]) -> None:
        self.selected = names

    def poll(
        self, inspection: Inspection | None, choices: tuple[ColumnChoice, ...]
    ) -> None:
        self.choices = choices
        if inspection is None:
            return
        available = {choice.name for choice in choices}
        self.selected = tuple(n for n in self.selected if n in available)
        if not self.selected and choices:
            self.selected = (choices[0].name,)
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
