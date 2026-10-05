"""Exact pooled category order, explicit missing values and aggregated tail."""

import numpy as np
import polars as pl

from datelier.core.column_roles import ColumnRole
from datelier.inspection.comparison_settings import ComparisonSettings, Normalization
from datelier.inspection.comparisons.types import (
    ComparisonInput,
    PreparedComparison,
    SeriesSummary,
)


def category_family(dtype: pl.DataType) -> str:
    if dtype in (pl.String, pl.Categorical) or isinstance(dtype, pl.Enum):
        return "string"
    if dtype == pl.Boolean:
        return "boolean"
    if dtype.is_integer():
        return "integer"
    return str(dtype)


def category_label(key: str | None, string: bool) -> str:
    value = "Missing (null)" if key is None else repr(key) if string else key
    return value if len(value) <= 80 else value[:77] + "…"


def categorical_comparison(
    inputs: tuple[ComparisonInput, ...], settings: ComparisonSettings
) -> PreparedComparison:
    originals = tuple(i.dataset.table.get_column(i.mapping.column) for i in inputs)
    families = {category_family(s.dtype) for s in originals}
    if len(families) != 1:
        raise ValueError(
            "Categorical mappings require compatible physical types "
            "(strings, booleans, integers or the same float type)"
        )
    counts = tuple(
        s.cast(pl.String).rename("key").value_counts().rename({"count": "n"})
        for s in originals
    )
    pooled = (
        pl.concat(counts)
        .group_by("key")
        .agg(pl.col("n").sum())
        .sort(["n", "key"], descending=[True, False], nulls_last=True)
    )
    keys: tuple[str | None, ...] = tuple(
        pooled.head(settings.category_limit).get_column("key").to_list()
    )
    other = pooled.height > len(keys)
    labels = tuple(category_label(key, "string" in families) for key in keys)
    # Long labels can coincide visually; keep every visible category distinct.
    labels = tuple(
        f"{label} [{n + 1}]" if labels.count(label) > 1 else label
        for n, label in enumerate(labels)
    )
    if other:
        labels += ("Other (remaining values)",)
    summaries: list[SeriesSummary] = []
    for source, original, frame in zip(inputs, originals, counts, strict=True):
        visible = frame.filter(
            pl.col("key").is_in(
                pl.Series(keys, dtype=pl.String).implode(), nulls_equal=True
            )
        )
        by_key = dict(visible.iter_rows())
        values = [int(by_key.get(key, 0)) for key in keys]
        if other:
            values.append(len(original) - sum(values))
        array = np.asarray(values, dtype=np.int64)
        heights = array.astype(np.float64)
        if settings.normalization == Normalization.DENSITY and len(original):
            heights /= len(original)
        modes = frame.filter(pl.col("key").is_not_null()).sort(
            ["n", "key"], descending=[True, False]
        )
        mode = modes.row(0) if modes.height else (None, 0)
        array.flags.writeable = heights.flags.writeable = False
        summaries.append(
            SeriesSummary(
                source.origin,
                source.mapping.label or source.filename,
                source.mapping.color,
                array,
                heights,
                len(original),
                len(original),
                original.null_count(),
                0,
                original.drop_nulls().n_unique(),
                category_label(mode[0], "string" in families)
                if mode[0] is not None
                else "—",
                int(mode[1]),
            )
        )
    return PreparedComparison(
        settings,
        ColumnRole.CATEGORY,
        tuple(summaries),
        labels=labels,
        keys=keys,
        other=other,
        note=(
            "Exact category counts, including nulls. Common order uses pooled "
            "frequency; ties sort by value. Other combines the remaining "
            "categories. Proportions divide by all rows in each file."
        ),
    )
