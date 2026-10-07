"""Exact dimension-bin selection from prepared records and current identities."""

import numpy as np
import polars as pl

from datelier.core.dataset import Dataset
from datelier.inspection.comparisons.types import ComparisonSelection, Origin
from datelier.inspection.images.comparisons.types import PreparedImageComparison
from datelier.plotting.selection import SELECTION_LIMIT


def select_dimension_bin(
    result: PreparedImageComparison,
    source: int,
    dimension: str,
    bin_index: int,
    dataset: Dataset,
) -> ComparisonSelection:
    if (
        not 0 <= source < len(result.profiles)
        or not 0 <= bin_index < result.settings.bins
    ):
        raise ValueError("Choose an available image source and common dimension bin")
    fields = {"Width": "width", "Height": "height", "Aspect ratio": "aspect_ratio"}
    if dimension not in fields:
        raise ValueError("Choose a supported image dimension")
    profile = result.profiles[source]
    if profile.revision != dataset.revision:
        raise ValueError("Image records changed; prepare their comparison again")
    summary = next(
        item for item in profile.dimension_summaries if item.key.name == dimension
    )
    bounds = result.bounds.get(summary.key)
    ready = profile.records.filter(pl.col("status") == "Ready")
    chosen = ready.clear()
    if bounds is not None and ready.height:
        values = np.asarray(ready[fields[dimension]].to_numpy(), dtype=np.longdouble)
        lo, hi = map(np.longdouble, bounds)
        normalized = (
            np.full(len(values), 0.5, dtype=np.longdouble)
            if lo == hi
            else (values - lo) / (hi - lo)
        )
        indices = np.minimum(
            (normalized * result.settings.bins).astype(np.int64),
            result.settings.bins - 1,
        )
        chosen = ready.filter(pl.Series(indices == bin_index))
    selected = chosen.head(SELECTION_LIMIT)
    first = selected["position"].min() if selected.height else None
    assert first is None or isinstance(first, int)
    return ComparisonSelection(
        Origin(
            profile.file_id,
            profile.revision,
            profile.settings.column or "",
            profile.view_name,
        ),
        tuple(int(row) for row in selected["row_id"]),
        chosen.height,
        first,
    )
