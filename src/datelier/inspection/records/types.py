"""Shared Inspect recipes and prepared record identities."""

from dataclasses import dataclass
from enum import StrEnum

import polars as pl

from datelier.core.dataset import DatasetRevision


class RecordMode(StrEnum):
    RANGE = "Row range"
    SELECTION = "Linked selection"
    RANDOM = "Seeded random sample"


@dataclass(frozen=True)
class InspectSettings:
    mode: RecordMode = RecordMode.RANGE
    start: int = 1
    count: int = 100
    seed: int = 42
    primary: str | None = None
    supporting: tuple[str, ...] | None = None
    gallery: bool = True
    focus: int = 0

    def validate(self) -> None:
        if (
            min(self.start, self.count) < 1
            or self.focus < 0
            or not 0 <= self.seed < 2**32
        ):
            raise ValueError(
                "Inspect requires positive range/count, nonnegative focus "
                "and a 32-bit seed"
            )
        if self.supporting is not None and len(set(self.supporting)) != len(
            self.supporting
        ):
            raise ValueError("Supporting columns must be distinct")


@dataclass(frozen=True)
class RecordSet:
    revision: DatasetRevision
    settings: InspectSettings
    positions: pl.Series
    row_ids: pl.Series
    eligible: int


@dataclass(frozen=True)
class RecordField:
    name: str
    text: str
    reference: str | None = None
    is_null: bool = False
    truncated: bool = False
    lines: tuple[str, ...] | None = None


@dataclass(frozen=True)
class RecordCard:
    row_id: int
    position: int
    primary: RecordField | None
    fields: tuple[RecordField, ...]


@dataclass(frozen=True)
class RecordPage:
    revision: DatasetRevision
    start: int
    cards: tuple[RecordCard, ...]
