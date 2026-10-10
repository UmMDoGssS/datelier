"""Shared column catalogs and explicit per-tool selection policies."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnChoice:
    name: str
    group: str = ""
    numeric: bool = False
    enabled: bool = True
    reason: str = ""


class SelectionPolicy(ABC):
    def permits(self, choice: ColumnChoice, selected: tuple[str, ...]) -> bool:
        return choice.enabled

    @abstractmethod
    def toggle(
        self, choices: tuple[ColumnChoice, ...], selected: tuple[str, ...], name: str
    ) -> tuple[str, ...]: ...

    def bulk(self, choices: tuple[ColumnChoice, ...]) -> tuple[str, ...]:
        selected: tuple[str, ...] = ()
        for choice in choices:
            if choice.enabled:
                selected = self.toggle(choices, selected, choice.name)
        return selected


@dataclass(frozen=True)
class MultiSelection(SelectionPolicy):
    limit: int | None = None
    catalog_order: bool = False

    def permits(self, choice: ColumnChoice, selected: tuple[str, ...]) -> bool:
        return choice.enabled and (
            choice.name in selected or self.limit is None or len(selected) < self.limit
        )

    def bulk(self, choices: tuple[ColumnChoice, ...]) -> tuple[str, ...]:
        names = tuple(c.name for c in choices if c.enabled)
        return names[: self.limit] if self.limit is not None else names

    def toggle(
        self, choices: tuple[ColumnChoice, ...], selected: tuple[str, ...], name: str
    ) -> tuple[str, ...]:
        choice = next((c for c in choices if c.name == name), None)
        if choice is None or not choice.enabled:
            return selected
        if name in selected:
            return tuple(n for n in selected if n != name)
        if self.limit is not None and len(selected) >= self.limit:
            return selected
        result = (*selected, name)
        return (
            tuple(c.name for c in choices if c.name in result)
            if self.catalog_order
            else result
        )


class SingleSelection(SelectionPolicy):
    def toggle(
        self, choices: tuple[ColumnChoice, ...], selected: tuple[str, ...], name: str
    ) -> tuple[str, ...]:
        return (
            (name,) if any(c.name == name and c.enabled for c in choices) else selected
        )

    def bulk(self, choices: tuple[ColumnChoice, ...]) -> tuple[str, ...]:
        return next(((c.name,) for c in choices if c.enabled), ())


class ProfileSelectionPolicy(MultiSelection):
    def __init__(self) -> None:
        super().__init__(catalog_order=True)

    def toggle(
        self, choices: tuple[ColumnChoice, ...], selected: tuple[str, ...], name: str
    ) -> tuple[str, ...]:
        choice = next((c for c in choices if c.name == name), None)
        if choice is None or not choice.enabled:
            return selected
        if name in selected:
            return tuple(n for n in selected if n != name)
        if not choice.numeric:
            return (name,)
        numerics = {c.name for c in choices if c.numeric}
        return super().toggle(
            choices, tuple(n for n in selected if n in numerics), name
        )

    def bulk(self, choices: tuple[ColumnChoice, ...]) -> tuple[str, ...]:
        return tuple(c.name for c in choices if c.numeric and c.enabled)
