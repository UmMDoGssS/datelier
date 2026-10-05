"""Exclusive categories and unrestricted numeric profile selection."""

from dataclasses import dataclass

from datelier.core.column_roles import ColumnRole, RoleInfo
from datelier.core.dataset import Dataset

PROFILE_ROLES = (ColumnRole.NUMERIC, ColumnRole.CATEGORY, ColumnRole.TEMPORAL)


@dataclass
class ProfileSelection:
    # None migrates an older single-column view; () is an intentional clear.
    columns: tuple[str, ...] | None = None
    choices: tuple[RoleInfo, ...] = ()

    def bind(self, dataset: Dataset, default: str | None = None) -> None:
        self.choices = tuple(i for i in dataset.roles or () if i.role in PROFILE_ROLES)
        allowed = {i.name: i.role for i in self.choices}
        if self.columns is None:
            self.columns = (
                (default,)
                if default in allowed
                else (self.choices[0].name,)
                if self.choices
                else ()
            )
        else:
            valid = tuple(dict.fromkeys(n for n in self.columns if n in allowed))
            # A role override can turn a selected numeric into a category.
            self.columns = (
                valid
                if all(allowed[n] == ColumnRole.NUMERIC for n in valid)
                else valid[:1]
            )

    def toggle(self, name: str) -> None:
        role = next(i.role for i in self.choices if i.name == name)
        current = self.columns or ()
        if name in current:
            self.columns = tuple(n for n in current if n != name)
        elif role != ColumnRole.NUMERIC:
            self.columns = (name,)
        else:
            numeric = {i.name for i in self.choices if i.role == ColumnRole.NUMERIC}
            selected = {*current, name} & numeric
            self.columns = tuple(i.name for i in self.choices if i.name in selected)

    def select_numeric(self) -> None:
        self.columns = tuple(
            i.name for i in self.choices if i.role == ColumnRole.NUMERIC
        )
