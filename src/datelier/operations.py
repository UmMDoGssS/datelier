"""Immutable, replayable table operations with independent source-row identity."""

from dataclasses import dataclass
from enum import StrEnum

import polars as pl

from datelier.dataset import Dataset
from datelier.scalars import Scalar
from datelier.transform_types import (
    CastColumn,
    DerivedColumn,
    DropMissing,
    FillMissing,
    Lookup,
    Transform,
)


class OperationFailure(ValueError):
    """A rejected edit; callers retain the previously published pipeline."""


class Comparison(StrEnum):
    EQ = "=="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    IS_NULL = "is null"
    NOT_NULL = "is not null"


@dataclass(frozen=True)
class Sort:
    columns: tuple[str, ...]
    descending: bool = False
    nulls_last: bool = True


@dataclass(frozen=True)
class Filter:
    column: str
    comparison: Comparison
    value: Scalar = None


@dataclass(frozen=True)
class SelectColumns:
    columns: tuple[str, ...]


type Operation = Sort | Filter | SelectColumns | Transform


def require_columns(table: pl.DataFrame, columns: tuple[str, ...]) -> None:
    if not columns or len(set(columns)) != len(columns):
        raise OperationFailure("Choose one or more distinct columns")
    for name in columns:
        if name not in table.columns:
            raise OperationFailure(f"Unknown column: {name!r}")


def filter_mask(series: pl.Series, operation: Filter) -> pl.Series:
    value = operation.value
    if operation.comparison not in (Comparison.IS_NULL, Comparison.NOT_NULL):
        if value is None:
            raise OperationFailure(
                "Use is null or is not null to filter missing values"
            )
        if isinstance(value, str) and series.dtype == pl.Date:
            value = pl.Series("value", [value]).str.to_date("%Y-%m-%d").item()
        elif isinstance(value, str) and isinstance(series.dtype, pl.Datetime):
            value = (
                pl.Series("value", [value])
                .str.to_datetime(
                    time_unit=series.dtype.time_unit, time_zone=series.dtype.time_zone
                )
                .item()
            )
    match operation.comparison:
        case Comparison.IS_NULL:
            return series.is_null()
        case Comparison.NOT_NULL:
            return series.is_not_null()
        case Comparison.EQ:
            return series == value
        case Comparison.NE:
            return series != value
        case Comparison.LT:
            return series < value
        case Comparison.LE:
            return series <= value
        case Comparison.GT:
            return series > value
        case Comparison.GE:
            return series >= value


def apply_operation(dataset: Dataset, operation: Operation) -> Dataset:
    table, ids = dataset.table, dataset.row_ids
    try:
        match operation:
            case Sort(columns, descending, nulls_last):
                require_columns(table, columns)
                # A collision-free internal column travels with rows, never exposed.
                name = "__datelier_identity"
                while name in table.columns:
                    name += "_"
                joined = table.with_columns(ids.alias(name))
                result = joined.sort(
                    [joined.get_column(column) for column in columns],
                    descending=descending,
                    nulls_last=nulls_last,
                    maintain_order=True,
                )
                ids = result.drop_in_place(name)
                table = result
            case Filter(column, _, _):
                require_columns(table, (column,))
                mask = filter_mask(
                    table.get_column(column).alias("value"), operation
                ).fill_null(False)
                table, ids = table.filter(mask), ids.filter(mask)
            case SelectColumns(columns):
                require_columns(table, columns)
                table = pl.DataFrame([table.get_column(name) for name in columns])
            case (
                CastColumn()
                | FillMissing()
                | DropMissing()
                | Lookup()
                | DerivedColumn()
            ):
                from datelier.transforms import apply_transform

                table, ids = apply_transform(table, ids, operation)
        return dataset.with_rows(table, ids)
    except OperationFailure:
        raise
    except Exception as error:
        raise OperationFailure(
            f"Could not apply {type(operation).__name__}: {error}"
        ) from error


def describe_operation(operation: Operation) -> str:
    match operation:
        case Sort(columns, descending, _):
            direction = "descending" if descending else "ascending"
            return f"Sort {', '.join(columns)} {direction}"
        case Filter(column, comparison, value):
            return f"Filter {column} {comparison.value} {value!r}"
        case SelectColumns(columns):
            return f"Keep {', '.join(columns)}"
        case CastColumn(column, dtype, strict):
            return f"Cast {column} to {dtype.value}" + (
                " (invalid values become null)" if not strict else ""
            )
        case FillMissing(column, value, nonfinite):
            return f"Fill missing {column} with {value!r}" + (
                " including nonfinite" if nonfinite else ""
            )
        case DropMissing(columns, nonfinite):
            return f"Drop rows missing {', '.join(columns)}" + (
                " including nonfinite" if nonfinite else ""
            )
        case DerivedColumn(name, expression, _):
            return f"Derive {name} = {expression}"
        case Lookup(column, entries, dtype, unmatched):
            return (
                f"Map {column}: {len(entries)} entries to {dtype.value}; "
                f"{unmatched.value}"
            )
