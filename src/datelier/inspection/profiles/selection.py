"""Exclusive nonnumeric fields and unrestricted numeric profile selection."""

from dataclasses import dataclass

import polars as pl

from datelier.core import Dataset
from datelier.core.column_roles import LIST_ROLES, PLOTTABLE_ROLES, ColumnRole, RoleInfo

PROFILE_ROLES = (
    *PLOTTABLE_ROLES,
    ColumnRole.TEXT,
    ColumnRole.IMAGE,
    *LIST_ROLES,
    ColumnRole.OBJECT,
)


@dataclass
class ProfileSelection:
    # None migrates an older single-column view; () is an intentional clear.
    columns: tuple[str, ...] | None = None
    choices: tuple[RoleInfo, ...] = ()

    def bind(self, dataset: Dataset, default: str | None = None) -> None:
        schema = dataset.table.schema
        self.choices = tuple(
            i
            for i in dataset.roles or ()
            if i.role in PROFILE_ROLES or schema[i.name] == pl.String
        )
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

    def text_column(self, prefer_text: bool = False) -> str | None:
        """Route String fields to text tools without changing their interpretation."""
        if not self.columns or len(self.columns) != 1:
            return None
        selected = next((i for i in self.choices if i.name == self.columns[0]), None)
        if selected is not None and selected.role == ColumnRole.LIST_TEXT:
            return selected.name
        if selected is not None and selected.dtype == str(pl.String):
            if selected.role == ColumnRole.IMAGE and not prefer_text:
                return None
            if prefer_text or selected.role not in PLOTTABLE_ROLES:
                return selected.name
        return None
