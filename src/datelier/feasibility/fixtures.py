import polars as pl


def make_table(rows: int, numeric_columns: int = 6) -> pl.DataFrame:
    """Deterministic mixed table; final numeric column has periodic nulls."""
    if rows < 0 or numeric_columns < 2:
        raise ValueError("Require nonnegative rows and at least two numeric columns")
    table = pl.DataFrame({"row_id": pl.int_range(0, rows, dtype=pl.UInt64, eager=True)})
    index = pl.col("row_id")
    features: list[pl.Expr] = []
    for column in range(numeric_columns):
        value = ((index * (column + 1) % 997).cast(pl.Float64) / 97).sin()
        value = value + (index % 3).cast(pl.Float64) * 4
        if column == numeric_columns - 1:
            value = pl.when(index % 17 == 0).then(None).otherwise(value)
        features.append(value.alias(f"feature_{column}"))
    return table.with_columns(
        *features, (pl.lit("group_") + (index % 3).cast(pl.String)).alias("category")
    )
