"""Physical histogram bounds shared by collection and cross-file commands."""

import numpy as np
import polars as pl

from datelier.inspection.images.moments import (
    ChannelMoments,
    histogram,
    normalized_values,
)
from datelier.inspection.images.profile_types import (
    ChannelKey,
    ChannelSummary,
    ImageBounds,
    ImageHistogram,
)


def bounds_for(
    key: ChannelKey, moments: ChannelMoments, shared: ImageBounds | None
) -> tuple[int | float | None, int | float | None]:
    if shared is not None and key in shared:
        return shared[key]
    return moments.minimum, moments.maximum


def dimension_histograms(
    records: pl.DataFrame, bins: int, shared: ImageBounds | None = None
) -> tuple[tuple[ImageHistogram, ...], tuple[ChannelSummary, ...]]:
    ready = records.filter(pl.col("status") == "Ready")
    charts: list[ImageHistogram] = []
    summaries: list[ChannelSummary] = []
    for name, label in (
        ("width", "Width"),
        ("height", "Height"),
        ("aspect_ratio", "Aspect ratio"),
    ):
        values = ready[name].to_numpy()
        moments = ChannelMoments()
        moments.add(values)
        key = ChannelKey("Dimensions", label, values.dtype.str)
        summaries.append(moments.summary(key))
        lo, hi = bounds_for(key, moments, shared)
        counts = np.zeros(bins, dtype=np.float64)
        if len(values) and lo is not None and hi is not None:
            normalized = normalized_values(values, lo, hi)
            counts[:] = np.histogram(normalized, np.linspace(0, 1, bins + 1))[0]
        charts.append(histogram(label, counts, lo, hi))
    return tuple(charts), tuple(summaries)
