"""Typed recipes for casts, missing values, and scalar lookup mappings."""

from dataclasses import dataclass
from enum import StrEnum

from datelier.scalars import Scalar


class TargetType(StrEnum):
    INT = "Int64"
    UINT = "UInt64"
    FLOAT = "Float64"
    BOOL = "Boolean"
    TEXT = "String"
    DATE = "Date"
    DATETIME = "Datetime"


class Unmatched(StrEnum):
    KEEP = "Keep original"
    NULL = "Set null"
    ERROR = "Reject unmatched"


@dataclass(frozen=True)
class CastColumn:
    column: str
    dtype: TargetType
    strict: bool = True


@dataclass(frozen=True)
class FillMissing:
    column: str
    value: Scalar
    include_nonfinite: bool = False


@dataclass(frozen=True)
class DropMissing:
    columns: tuple[str, ...]
    include_nonfinite: bool = False


@dataclass(frozen=True)
class Lookup:
    column: str
    entries: tuple[tuple[Scalar, Scalar], ...]
    dtype: TargetType
    unmatched: Unmatched = Unmatched.KEEP


@dataclass(frozen=True)
class DerivedColumn:
    name: str
    expression: str
    replace: bool = False


type Transform = CastColumn | FillMissing | DropMissing | Lookup | DerivedColumn
