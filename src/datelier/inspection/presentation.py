"""Typed bounded cell metadata and worker-prepared numeric display ranges."""

import hashlib
import math
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

import polars as pl

from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset


class NumericScale(StrEnum):
    PERCENTILE = "Percentile (2–98)"
    LINEAR = "Linear min/max"
    CUSTOM = "Custom range"


@dataclass(frozen=True)
class TablePresentation:
    enabled: bool = True
    scale: NumericScale = NumericScale.PERCENTILE
    minimum: float = 0
    maximum: float = 1
    badges: bool = True

    def validate(self) -> None:
        if (
            not math.isfinite(self.minimum)
            or not math.isfinite(self.maximum)
            or self.minimum >= self.maximum
        ):
            raise ValueError("Custom shading range must have finite minimum < maximum")


@dataclass(frozen=True)
class NumericBounds:
    column: str
    minimum: float
    maximum: float
    percentile_low: float
    percentile_high: float


@dataclass(frozen=True)
class CellPresentation:
    is_null: bool
    number: float | None = None
    category: int | None = None
    nonfinite: bool = False


@dataclass(frozen=True)
class CellStyle:
    rgba: tuple[float, float, float] | None = None
    marker: str = ""


def prepare_bounds(dataset: Dataset) -> tuple[NumericBounds, ...]:
    result: list[NumericBounds] = []
    table = dataset.table
    for name in dataset.columns_for(ColumnRole.NUMERIC):
        values = table.get_column(name).rename("value").cast(pl.Float64)
        finite = values.filter(values.is_finite())
        if not len(finite):
            continue
        lo, hi = finite.min(), finite.max()
        qlo = finite.quantile(0.02, interpolation="linear")
        qhi = finite.quantile(0.98, interpolation="linear")
        assert isinstance(lo, float) and isinstance(hi, float)
        assert qlo is not None and qhi is not None
        if not math.isfinite(qlo) or not math.isfinite(qhi):
            qlo, qhi = lo, hi
        result.append(NumericBounds(name, lo, hi, qlo, qhi))
    return tuple(result)


def prepare_cell(value: object, role: ColumnRole) -> CellPresentation:
    if value is None:
        return CellPresentation(True)
    if role == ColumnRole.NUMERIC:
        if not isinstance(value, (int, float, Decimal)):
            return CellPresentation(False)
        try:
            number = float(value)
        except ValueError, OverflowError:
            return CellPresentation(False)
        return CellPresentation(
            False, number=number, nonfinite=not math.isfinite(number)
        )
    if role == ColumnRole.CATEGORY:
        encoded = f"{type(value).__name__}:{value}".encode()
        category = int.from_bytes(
            hashlib.blake2b(encoded, digest_size=2).digest(), "little"
        )
        return CellPresentation(False, category=category)
    return CellPresentation(False)


def cell_style(
    cell: CellPresentation, bounds: NumericBounds | None, settings: TablePresentation
) -> CellStyle:
    """Pure per-cell palette lookup; no I/O, parsing or table-wide work."""
    if not settings.enabled:
        return CellStyle()
    if cell.is_null:
        return CellStyle((0.7, 0.4, 0.15), "(null)")
    if cell.nonfinite:
        return CellStyle((0.55, 0.45, 0.55), "!")
    if cell.category is not None:
        # Fixed bounded colors keep even high-cardinality labels readable.
        palette = (
            (0.3, 0.65, 0.8),
            (0.8, 0.5, 0.3),
            (0.4, 0.7, 0.4),
            (0.7, 0.4, 0.65),
            (0.7, 0.65, 0.3),
            (0.5, 0.5, 0.8),
        )
        return CellStyle(palette[cell.category % len(palette)])
    if cell.number is None or bounds is None:
        return CellStyle()
    if settings.scale == NumericScale.CUSTOM:
        lo, hi = settings.minimum, settings.maximum
    elif settings.scale == NumericScale.LINEAR:
        lo, hi = bounds.minimum, bounds.maximum
    else:
        lo, hi = bounds.percentile_low, bounds.percentile_high
    value = cell.number
    magnitude = max(abs(lo), abs(hi), abs(value)) or 1
    low, high = lo / magnitude, hi / magnitude
    position = (
        max(0.0, min(1.0, (value / magnitude - low) / (high - low)))
        if high > low
        else 0.5
    )
    marker = "<" if value < lo else ">" if value > hi else "=" if lo == hi else ""
    return CellStyle((0.2 + 0.65 * position, 0.35, 0.85 - 0.65 * position), marker)
