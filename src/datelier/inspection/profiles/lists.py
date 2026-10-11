"""Exact list lengths/shapes and flattened leaves, prepared with Polars in workers."""

from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True)
class ListDimension:
    depth: int
    containers: int
    nulls: int
    empty: int
    minimum: int | None
    maximum: int | None
    mean: float | None
    median: float | None


@dataclass(frozen=True)
class ListStatistics:
    dimensions: tuple[ListDimension, ...]
    elements: int
    null_elements: int
    rectangular: int
    ragged: int
    unknown: int
    shapes: tuple[tuple[str, int], ...]
    other_shapes: int


def _lists(series: pl.Series) -> pl.Series:
    return series.arr.to_list() if isinstance(series.dtype, pl.Array) else series


def flatten_elements(series: pl.Series) -> pl.Series:
    """Empty/null containers contribute no leaves; explicit null leaves remain."""
    while isinstance(series.dtype, (pl.List, pl.Array)):
        series = _lists(series).drop_nulls()
        series = series.filter(series.list.len() > 0).explode(empty_as_null=False)
    return series


def _shape(value: pl.Expr, dtype: pl.DataType) -> pl.Expr:
    if not isinstance(dtype, (pl.List, pl.Array)):
        raise ValueError("Shape requires a list or fixed-size array")
    inner = dtype.inner
    if isinstance(dtype, pl.Array):
        value = value.arr.to_list()
    length = value.list.len().cast(pl.String)
    if not isinstance(inner, (pl.List, pl.Array)):
        return length
    child = value.list.eval(_shape(pl.element(), inner))
    return (
        pl.when(value.is_null())
        .then(None)
        .when(value.list.len() == 0)
        .then(length + " × ?")
        .when(child.list.contains("ragged"))
        .then(pl.lit("ragged"))
        .when(child.list.eval(pl.element().is_null()).list.any())
        .then(pl.lit("unknown"))
        .when(child.list.n_unique() != 1)
        .then(pl.lit("ragged"))
        .otherwise(length + " × " + child.list.first())
    )


def prepare_list(series: pl.Series) -> tuple[pl.Series, ListStatistics]:
    if not isinstance(series.dtype, (pl.List, pl.Array)):
        raise ValueError("List statistics require a list or fixed-size array column")
    dimensions: list[ListDimension] = []
    values = series
    while isinstance(values.dtype, (pl.List, pl.Array)):
        values = _lists(values)
        lengths = values.list.len().drop_nulls()
        summary = (
            lengths.to_frame("length")
            .select(
                pl.col("length").min(),
                pl.col("length").max().alias("maximum"),
                pl.col("length").mean().alias("mean"),
                pl.col("length").median().alias("median"),
            )
            .row(0)
        )
        dimensions.append(
            ListDimension(
                len(dimensions) + 1,
                len(values),
                values.null_count(),
                int((lengths == 0).sum()),
                int(summary[0]) if summary[0] is not None else None,
                int(summary[1]) if summary[1] is not None else None,
                float(summary[2]) if summary[2] is not None else None,
                float(summary[3]) if summary[3] is not None else None,
            )
        )
        values = values.drop_nulls()
        values = values.filter(values.list.len() > 0).explode(empty_as_null=False)
    shapes = (
        series.rename("value")
        .to_frame()
        .select(_shape(pl.col("value"), series.dtype).alias("shape"))
        .to_series()
        .drop_nulls()
    )
    counts = shapes.value_counts().sort(["count", "shape"], descending=[True, False])
    ragged = int((shapes == "ragged").sum())
    unknown = int((shapes.str.contains(r"\?|unknown")).sum())
    return values, ListStatistics(
        tuple(dimensions),
        len(values),
        values.null_count(),
        len(shapes) - ragged - unknown,
        ragged,
        unknown,
        tuple((str(shape), int(count)) for shape, count in counts.head(12).iter_rows()),
        int(counts.tail(max(0, counts.height - 12)).get_column("count").sum()),
    )
