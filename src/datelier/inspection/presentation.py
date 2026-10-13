"""Typed bounded cell metadata and worker-prepared numeric display ranges."""

import hashlib
import math
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

import polars as pl

from datelier.core import ColumnRole, Dataset
from datelier.core.column_roles import REFERENCE_ROLES
from datelier.inspection.arrays.means import list_element_means


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
    text_length: float | None = None
    bounds: NumericBounds | None = None
    note: str = ""


@dataclass(frozen=True)
class CellStyle:
    rgba: tuple[float, float, float] | None = None
    marker: str = ""
    foreground: tuple[float, float, float] | None = None
    bold: bool = False
    opaque: bool = False


def prepare_bounds(dataset: Dataset) -> tuple[NumericBounds, ...]:
    result: list[NumericBounds] = []
    table = dataset.table
    strings = tuple(
        name
        for name, dtype in table.schema.items()
        if (dtype in (pl.String, pl.Categorical) or isinstance(dtype, pl.Enum))
        and dataset.role(name).role != ColumnRole.IDENTIFIER
    )
    containers = tuple(
        name
        for name, dtype in table.schema.items()
        if isinstance(dtype, (pl.List, pl.Array))
        and dataset.role(name).role != ColumnRole.LIST_IDENTIFIER
    )
    for name in (
        *dataset.columns_for(ColumnRole.NUMERIC),
        *strings,
        *containers,
    ):
        values = table.get_column(name).rename("value")
        if name in strings:
            values = values.cast(pl.String).str.len_chars()
        elif name in containers:
            values = list_element_means(values).values
        values = values.cast(pl.Float64)
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
    if role in (ColumnRole.IDENTIFIER, ColumnRole.LIST_IDENTIFIER):
        return CellPresentation(False)
    if role in (
        ColumnRole.TEXT,
        *REFERENCE_ROLES,
    ) and isinstance(value, str):
        return CellPresentation(False, text_length=len(value))
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
        return CellPresentation(
            False,
            category=category,
            text_length=len(value) if isinstance(value, str) else None,
        )
    return CellPresentation(False)


def prepare_column_cells(
    series: pl.Series, role: ColumnRole
) -> tuple[CellPresentation, ...]:
    if not isinstance(series.dtype, (pl.List, pl.Array)):
        return tuple(prepare_cell(value, role) for value in series)
    nulls = series.is_null().to_list()
    if role == ColumnRole.LIST_IDENTIFIER:
        return tuple(CellPresentation(bool(value)) for value in nulls)
    means = list_element_means(series)
    return tuple(
        CellPresentation(
            bool(null),
            number=None if means.text else value,
            text_length=value if means.text else None,
            nonfinite=value is None and invalid > 0,
            note=f"Mean of {count:,} "
            + ("text lengths" if means.text else "finite numeric elements")
            + (f"; {invalid:,} nonfinite elements excluded" if invalid else ""),
        )
        for null, value, count, invalid in zip(
            nulls,
            means.values.to_list(),
            means.counts.to_list(),
            means.nonfinites.to_list(),
            strict=True,
        )
    )


def cell_style(
    cell: CellPresentation, bounds: NumericBounds | None, settings: TablePresentation
) -> CellStyle:
    """Pure per-cell palette lookup; no I/O, parsing or table-wide work."""
    if not settings.enabled:
        return CellStyle()
    if cell.is_null:
        return CellStyle((1, 1, 1), "(null)", (0, 0, 0), True, True)
    if cell.nonfinite:
        return CellStyle((0.55, 0.45, 0.55), "!")
    if cell.category is not None and cell.text_length is None:
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
    bounds = cell.bounds or bounds
    value = float(cell.text_length) if cell.text_length is not None else cell.number
    if value is None or bounds is None:
        return CellStyle()
    if settings.scale == NumericScale.CUSTOM:
        lo, hi = settings.minimum, settings.maximum
    elif settings.scale == NumericScale.LINEAR:
        lo, hi = bounds.minimum, bounds.maximum
    else:
        lo, hi = bounds.percentile_low, bounds.percentile_high
    magnitude = max(abs(lo), abs(hi), abs(value)) or 1
    low, high = lo / magnitude, hi / magnitude
    position = (
        0.0
        if value < lo
        else 1.0
        if value > hi
        else (
            max(0.0, min(1.0, (value / magnitude - low) / (high - low)))
            if high > low
            else 0.5
        )
    )
    marker = "<" if value < lo else ">" if value > hi else "=" if lo == hi else ""
    color = (
        crest(position)
        if cell.text_length is not None
        else (0.2 + 0.65 * position, 0.35, 0.85 - 0.65 * position)
    )
    return CellStyle(color, marker)


def crest(position: float) -> tuple[float, float, float]:
    """Interpolate Seaborn Crest samples without importing a plotting runtime.

    Samples from seaborn/cm.py (v0.13.2), _crest_lut, indices 0:256:32
    plus the final entry. Seaborn is BSD licensed; palette values are data.
    """
    anchors = (
        (0.6468274, 0.80289262, 0.56592265),
        (0.50711872, 0.73665492, 0.56821764),
        (0.37890483, 0.66859548, 0.56566462),
        (0.28251558, 0.59517119, 0.56181204),
        (0.20094292, 0.52087429, 0.55342884),
        (0.12709242, 0.44601517, 0.54438795),
        (0.11646936, 0.36578429, 0.52726234),
        (0.15138673, 0.27982444, 0.49119848),
        (0.17363177, 0.19076859, 0.44549087),
    )
    scaled = max(0, min(1, position)) * (len(anchors) - 1)
    index = min(int(scaled), len(anchors) - 2)
    fraction = scaled - index
    lo, hi = anchors[index], anchors[index + 1]
    return (
        lo[0] + fraction * (hi[0] - lo[0]),
        lo[1] + fraction * (hi[1] - lo[1]),
        lo[2] + fraction * (hi[2] - lo[2]),
    )
