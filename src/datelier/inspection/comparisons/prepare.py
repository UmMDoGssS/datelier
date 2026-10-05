"""Worker entry points for comparisons and source-specific bin selections."""

import polars as pl

from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset
from datelier.inspection.comparison_settings import ComparisonSettings
from datelier.inspection.comparisons.categorical import categorical_comparison
from datelier.inspection.comparisons.numeric import numeric_comparison
from datelier.inspection.comparisons.types import (
    ComparisonInput,
    ComparisonSelection,
    PreparedComparison,
)
from datelier.plotting.selection import SELECTION_LIMIT


def prepare_comparison(
    inputs: tuple[ComparisonInput, ...], settings: ComparisonSettings
) -> PreparedComparison:
    settings.validate()
    if len(inputs) < 2 or tuple(i.mapping for i in inputs) != settings.sources:
        raise ValueError("Map columns from at least two available files")
    for source in inputs:
        if source.mapping.column not in source.dataset.table.columns:
            raise ValueError(
                f"{source.filename}: column {source.mapping.column!r} is unavailable"
            )
    roles = {i.dataset.role(i.mapping.column).role for i in inputs}
    if roles == {ColumnRole.NUMERIC}:
        return numeric_comparison(inputs, settings)
    if roles == {ColumnRole.CATEGORY}:
        return categorical_comparison(inputs, settings)
    raise ValueError(
        "Map compatible Numeric columns or Categorical columns; "
        "change analysis roles in Schema when needed"
    )


def select_bin(
    result: PreparedComparison, series_index: int, bin_index: int, dataset: Dataset
) -> ComparisonSelection:
    series = result.series[series_index]
    if dataset.revision != series.origin.revision:
        raise ValueError(
            "The mapped file changed; obsolete comparison selection ignored"
        )
    if not 0 <= bin_index < len(series.counts):
        raise ValueError("Choose a displayed bin/category")
    column = dataset.table.get_column(series.origin.column)
    if result.kind == ColumnRole.NUMERIC:
        values = column.cast(pl.Float64) / result.scale
        lower, upper = result.edges[bin_index : bin_index + 2]
        mask = (
            values.is_finite()
            & (values <= upper)
            & ((values >= lower) if bin_index == 0 else (values > lower))
        )
    else:
        values = column.cast(pl.String)
        if result.other and bin_index == len(result.keys):
            mask = ~values.is_in(
                pl.Series(result.keys, dtype=pl.String).implode(), nulls_equal=True
            )
        else:
            key = result.keys[bin_index]
            mask = values.is_null() if key is None else values == key
    frame = pl.DataFrame(
        {
            "row": dataset.row_ids,
            "position": pl.Series(range(len(column)), dtype=pl.UInt64),
        }
    )
    matches = frame.filter(mask)
    ids = tuple(matches.head(SELECTION_LIMIT).get_column("row").to_list())
    first = int(matches.item(0, "position")) if matches.height else None
    return ComparisonSelection(series.origin, ids, matches.height, first)
