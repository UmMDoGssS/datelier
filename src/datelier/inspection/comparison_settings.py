"""Explicit cross-file mappings and persisted profile display settings."""

import math
from dataclasses import dataclass
from enum import StrEnum


class Normalization(StrEnum):
    COUNT = "Count"
    DENSITY = "Density / proportion"


@dataclass(frozen=True)
class ComparisonSource:
    file_id: str
    column: str
    label: str = ""
    color: tuple[float, float, float, float] | None = None

    def validate(self) -> None:
        if not self.file_id or not self.column:
            raise ValueError("Comparison mappings require a file and column")
        if self.color is not None and (
            len(self.color) != 4
            or any(
                not math.isfinite(value) or not 0 <= value <= 1 for value in self.color
            )
        ):
            raise ValueError("Comparison colors require finite RGBA values in [0, 1]")


@dataclass(frozen=True)
class ComparisonSettings:
    sources: tuple[ComparisonSource, ...] = ()
    bins: int = 20
    category_limit: int = 20
    normalization: Normalization = Normalization.DENSITY

    def validate(self) -> None:
        if not 1 <= self.bins <= 100 or not 1 <= self.category_limit <= 100:
            raise ValueError("Comparison bins/category limits must be in [1, 100]")
        if len(self.sources) > 32 or len(
            {source.file_id for source in self.sources}
        ) != len(self.sources):
            raise ValueError("Choose one column per file and at most 32 mapped files")
        for source in self.sources:
            source.validate()
