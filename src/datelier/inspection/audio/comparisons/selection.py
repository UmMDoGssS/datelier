"""Prepared scalar-bin selections return only the contributing source's identities."""

import polars as pl

from datelier.core.dataset import Dataset
from datelier.inspection.audio.comparisons.distributions import (
    metric_records,
    normalized_values,
)
from datelier.inspection.audio.comparisons.types import (
    AudioMetric,
    PreparedAudioComparison,
)
from datelier.inspection.comparisons.types import ComparisonSelection, Origin
from datelier.plotting.scatter import SELECTION_LIMIT


def select_bin(
    result: PreparedAudioComparison,
    source: int,
    metric: AudioMetric,
    bin_index: int,
    dataset: Dataset,
) -> ComparisonSelection:
    curve = next((curve for curve in result.curves if curve.metric == metric), None)
    if (
        curve is None
        or not 0 <= source < len(result.profiles)
        or not 0 <= bin_index < result.settings.bins
    ):
        raise ValueError("Choose a current audio source, metric and bin")
    profile = result.profiles[source]
    if profile.revision != dataset.revision:
        raise ValueError("Audio records changed; prepare their comparison again")
    rows = metric_records(profile, metric).filter(
        pl.col(metric.field).is_not_null() & pl.col(metric.field).is_finite()
    )
    chosen = rows.clear()
    if rows.height and curve.minimum is not None and curve.maximum is not None:
        values = rows[metric.field].cast(pl.Float64).to_numpy()
        if curve.scaled:
            values = normalized_values(values, curve.minimum, curve.maximum)
        lo, hi = curve.edges[bin_index : bin_index + 2]
        mask = (values >= lo) & (
            values <= hi if bin_index == result.settings.bins - 1 else values < hi
        )
        chosen = rows.filter(pl.Series(mask)).unique(
            subset="row_id", maintain_order=True
        )
    ids = tuple(int(row) for row in chosen["row_id"].head(SELECTION_LIMIT))
    positions = (
        pl.DataFrame({"row_id": dataset.row_ids})
        .with_row_index("position")
        .filter(pl.col("row_id").is_in(ids))
    )
    first = positions["position"].min() if positions.height else None
    assert first is None or isinstance(first, int)
    return ComparisonSelection(
        Origin(
            profile.file_id,
            profile.revision,
            profile.settings.column or "",
            profile.view_name,
        ),
        ids,
        chosen.height,
        first,
    )
