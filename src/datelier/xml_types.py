"""Deterministic, whole-column scalar inference for XML text fields."""

import polars as pl

INTEGER = r"^[+-]?[0-9]+$"
NUMBER = r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$"


def infer_xml_types(table: pl.DataFrame, *, dates: bool) -> pl.DataFrame:
    expressions: list[pl.Expr] = []
    for name in table.columns:
        values = table[name].drop_nulls()
        column = pl.col(name)
        if len(values):
            if values.is_in(["true", "false"]).all():
                column = column == "true"
            elif values.str.contains(INTEGER).all():
                column = column.cast(pl.Int64, strict=True)
            elif values.str.contains(NUMBER).all():
                numeric = values.cast(pl.Float64, strict=True)
                if not numeric.is_finite().all():
                    raise ValueError(
                        f"Field {name!r} exceeds finite numeric range; read as text."
                    )
                column = column.cast(pl.Float64, strict=True)
            elif dates:
                parsed = values.str.to_date(format="%Y-%m-%d", strict=False)
                if parsed.null_count() == 0:
                    column = column.str.to_date(format="%Y-%m-%d", strict=True)
        expressions.append(column.alias(name))
    return table.select(expressions)
