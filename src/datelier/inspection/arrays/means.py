"""Bounded scalar reductions for list and array cell presentation."""

from dataclasses import dataclass

import polars as pl

from datelier.core.column_roles import list_leaf_dtype


@dataclass(frozen=True)
class ElementMeans:
    values: pl.Series
    counts: pl.Series
    nonfinites: pl.Series
    text: bool = False


def _reduce_lists(series: pl.Series) -> ElementMeans:
    values = series.arr.to_list() if isinstance(series.dtype, pl.Array) else series
    while isinstance(values.dtype, pl.List) and isinstance(
        values.dtype.inner, (pl.List, pl.Array)
    ):
        element = pl.element()
        if isinstance(values.dtype.inner, pl.Array):
            element = element.arr.to_list()
        values = values.list.eval(
            element.explode(empty_as_null=False, keep_nulls=False)
        )
    leaf = list_leaf_dtype(values.dtype)
    text = leaf in (pl.String, pl.Categorical) or isinstance(leaf, pl.Enum)
    if text:
        values = values.list.eval(
            pl.element().cast(pl.String).str.len_chars().cast(pl.Float64)
        )
        invalid = pl.Series("invalid", [0] * len(values), dtype=pl.UInt32)
    elif leaf.is_numeric() or leaf in (pl.Boolean, pl.Null):
        values = values.list.eval(pl.element().cast(pl.Float64))
        invalid = (
            values.list.eval(pl.element().is_not_null() & ~pl.element().is_finite())
            .list.sum()
            .fill_null(0)
        )
        values = values.list.eval(
            pl.when(pl.element().is_finite()).then(pl.element()).otherwise(None)
        )
    else:
        return ElementMeans(
            pl.Series("mean", [None] * len(values), dtype=pl.Float64),
            pl.Series("count", [0] * len(values), dtype=pl.UInt32),
            pl.Series("invalid", [0] * len(values), dtype=pl.UInt32),
        )
    counts = values.list.eval(pl.element().is_not_null()).list.sum().fill_null(0)
    # Normalize within each row before averaging to avoid overflow in sums.
    magnitude = pl.element().abs().max()
    normalized = values.list.eval(
        pl.element() / pl.when(magnitude > 0).then(magnitude).otherwise(1)
    )
    means = normalized.list.mean() * values.list.eval(pl.element().abs()).list.max()
    return ElementMeans(means, counts, invalid, text)


def list_element_means(series: pl.Series) -> ElementMeans:
    """Flatten ragged leaves per record; never take a mean of child means."""
    if not isinstance(series.dtype, (pl.List, pl.Array)):
        raise ValueError("Element means require a List or Array column")
    chunks = [
        _reduce_lists(series.slice(start, 2048))
        for start in range(0, max(1, len(series)), 2048)
    ]
    return ElementMeans(
        pl.concat([chunk.values for chunk in chunks]),
        pl.concat([chunk.counts for chunk in chunks]),
        pl.concat([chunk.nonfinites for chunk in chunks]),
        chunks[0].text,
    )
