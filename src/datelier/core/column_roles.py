"""Column meaning inferred in data workers, with explicit user overrides."""

import re
from dataclasses import dataclass
from enum import StrEnum

import polars as pl


class ColumnRole(StrEnum):
    NUMERIC = "Numeric"
    CATEGORY = "Categorical"
    TEXT = "Text"
    IDENTIFIER = "Identifier"
    TEMPORAL = "Temporal"
    UNSUPPORTED = "Unsupported"


@dataclass(frozen=True)
class RoleInfo:
    name: str
    dtype: str
    inferred: ColumnRole
    distinct: int | None
    nonnull: int
    reason: str
    override: ColumnRole | None = None

    @property
    def role(self) -> ColumnRole:
        return self.override or self.inferred


def allowed_roles(dtype: pl.DataType) -> tuple[ColumnRole, ...]:
    if dtype.is_numeric():
        return (ColumnRole.NUMERIC, ColumnRole.CATEGORY, ColumnRole.IDENTIFIER)
    if dtype == pl.String:
        return (ColumnRole.CATEGORY, ColumnRole.TEXT, ColumnRole.IDENTIFIER)
    if dtype in (pl.Boolean, pl.Categorical) or isinstance(dtype, pl.Enum):
        return (ColumnRole.CATEGORY, ColumnRole.IDENTIFIER)
    if dtype.is_temporal():
        return (ColumnRole.TEMPORAL,)
    return (ColumnRole.UNSUPPORTED,)


def infer_roles(
    table: pl.DataFrame, previous: tuple[RoleInfo, ...] = ()
) -> tuple[RoleInfo, ...]:
    overrides = {p.name: p.override for p in previous if p.override is not None}
    result: list[RoleInfo] = []
    for series in table:
        dtype = series.dtype
        nonnull = len(series) - series.null_count()
        distinct = (
            series.n_unique() - int(series.null_count() > 0)
            if allowed_roles(dtype) != (ColumnRole.UNSUPPORTED,)
            else None
        )
        unique = bool(nonnull and distinct == nonnull)
        # A unique integer feature alone is insufficient evidence of an ID.
        words = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", series.name).lower()
        id_name = bool(re.search(r"(^|[^a-z0-9])(id|index)($|[^a-z0-9])", words))
        if dtype.is_integer() and unique and id_name:
            inferred = ColumnRole.IDENTIFIER
            reason = "Unique non-null integers with an ID/index name."
        elif dtype == pl.String and unique:
            inferred = ColumnRole.TEXT
            reason = "Every non-null string is unique."
        elif dtype == pl.String:
            inferred = ColumnRole.CATEGORY
            reason = "Repeated string values form categories."
        else:
            inferred = allowed_roles(dtype)[0]
            reason = f"Inferred from {dtype}."
        override = overrides.get(series.name)
        if override not in allowed_roles(dtype):
            override = None
        result.append(
            RoleInfo(
                series.name, str(dtype), inferred, distinct, nonnull, reason, override
            )
        )
    return tuple(result)
