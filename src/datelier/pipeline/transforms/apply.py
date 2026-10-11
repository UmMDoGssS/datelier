"""Polars implementations of typed transform recipes."""

import polars as pl

from datelier.core.scalars import Scalar
from datelier.pipeline.operations import OperationFailure, require_columns
from datelier.pipeline.transforms.types import (
    CastColumn,
    DerivedColumn,
    DropMissing,
    FillMissing,
    Lookup,
    TargetType,
    Transform,
    Unmatched,
)


def target_dtype(dtype: TargetType) -> pl.DataType:
    return {
        TargetType.INT: pl.Int64(),
        TargetType.UINT: pl.UInt64(),
        TargetType.FLOAT: pl.Float64(),
        TargetType.BOOL: pl.Boolean(),
        TargetType.TEXT: pl.String(),
        TargetType.DATE: pl.Date(),
        TargetType.DATETIME: pl.Datetime("us"),
    }[dtype]


def scalar_series(value: Scalar, dtype: pl.DataType) -> pl.Series:
    # Casting uses the same strict contract as a full column, never silently
    # truncating/reinterpreting a mixed lookup value through constructor inference.
    return pl.Series("value", [value]).cast(dtype, strict=True)


def missing_mask(series: pl.Series, nonfinite: bool) -> pl.Series:
    series = series.alias("value")
    mask = series.is_null()
    if nonfinite and series.dtype.is_float():
        mask = mask | ~series.is_finite().fill_null(False)
    return mask


def apply_transform(
    table: pl.DataFrame, ids: pl.Series, operation: Transform
) -> tuple[pl.DataFrame, pl.Series]:
    if isinstance(operation, DerivedColumn):
        from datelier.pipeline.transforms.expressions import derive_column

        return derive_column(
            table, operation.name, operation.expression, operation.replace
        ), ids
    if isinstance(operation, DropMissing):
        require_columns(table, operation.columns)
        mask = pl.Series("missing", [False] * table.height)
        for name in operation.columns:
            mask = mask | missing_mask(
                table.get_column(name), operation.include_nonfinite
            )
        return table.filter(~mask), ids.filter(~mask)
    require_columns(table, (operation.column,))
    series = table.get_column(operation.column).alias("value")
    match operation:
        case CastColumn(_, dtype, strict):
            if series.dtype == pl.String and dtype == TargetType.DATE:
                result = series.str.to_date("%Y-%m-%d", strict=strict)
            elif series.dtype == pl.String and dtype == TargetType.DATETIME:
                result = series.str.to_datetime(time_unit="us", strict=strict)
            else:
                result = series.cast(target_dtype(dtype), strict=strict)
        case FillMissing(_, value, nonfinite):
            if value is None:
                raise OperationFailure("Choose a non-null replacement value")
            replacement = scalar_series(value, series.dtype).item()
            result = table.select(
                pl.when(pl.lit(missing_mask(series, nonfinite)))
                .then(pl.lit(replacement, dtype=series.dtype))
                .otherwise(pl.lit(series))
                .alias("value")
            ).to_series()
        case Lookup(_, entries, dtype, unmatched):
            if not entries:
                raise OperationFailure("Provide at least one lookup entry")
            keys = [scalar_series(key, series.dtype).item() for key, _ in entries]
            if len(set(keys)) != len(keys):
                raise OperationFailure("Lookup keys must be distinct after conversion")
            values = [
                scalar_series(value, target_dtype(dtype)).item() for _, value in entries
            ]
            expression = pl.lit(series)
            kwargs = {}  # Default omitted for strict unmatched rejection.
            if unmatched == Unmatched.KEEP:
                kwargs["default"] = expression
            elif unmatched == Unmatched.NULL:
                kwargs["default"] = pl.lit(None)
            result = table.select(
                expression.replace_strict(
                    keys, values, return_dtype=target_dtype(dtype), **kwargs
                ).alias("value")
            ).to_series()
    return table.with_columns(result.alias(operation.column)), ids
