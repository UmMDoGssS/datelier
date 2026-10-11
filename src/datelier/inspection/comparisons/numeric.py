"""Exact common-bin numeric histograms and finite-value summaries."""

import math

import numpy as np
import polars as pl

from datelier.core import ColumnRole
from datelier.inspection.comparison_settings import ComparisonSettings, Normalization
from datelier.inspection.comparisons.types import (
    ComparisonInput,
    PreparedComparison,
    SeriesSummary,
)
from datelier.inspection.profiles import prepare_numeric_statistics


def numeric_comparison(
    inputs: tuple[ComparisonInput, ...], settings: ComparisonSettings
) -> PreparedComparison:
    originals = tuple(i.dataset.table.get_column(i.mapping.column) for i in inputs)
    finite = tuple(
        s.cast(pl.Float64).filter(s.cast(pl.Float64).is_finite()) for s in originals
    )
    extrema = [
        float(value)
        for s in finite
        if len(s)
        for value in (s.min(), s.max())
        if isinstance(value, (int, float))
    ]
    if not extrema:
        raise ValueError("No finite values in the mapped numeric columns")
    low, high = min(extrema), max(extrema)
    magnitude = max(abs(low), abs(high))
    scale = (
        magnitude if magnitude and (magnitude > 1e150 or magnitude < 1e-150) else 1.0
    )
    scaled = tuple(values / scale for values in finite)
    scaled_extrema = [
        float(v)
        for s in scaled
        if len(s)
        for v in (s.min(), s.max())
        if isinstance(v, (int, float))
    ]
    lower, upper = min(scaled_extrema), max(scaled_extrema)
    if lower == upper:
        margin = max(0.5, abs(lower) * 1e-6)
        lower, upper = lower - margin, upper + margin
    edges = tuple(
        dict.fromkeys(
            edge
            for n in range(settings.bins)
            if (edge := lower + (upper - lower) * n / settings.bins) < upper
        )
    ) + (upper,)
    widths = np.diff(edges)
    summaries: list[SeriesSummary] = []
    for source, original, values in zip(inputs, originals, scaled, strict=True):
        stats = prepare_numeric_statistics(original)
        counts = np.asarray(
            values.hist(bins=list(edges)).get_column("count"), dtype=np.int64
        )
        if int(counts.sum()) != len(values):
            raise ValueError(
                f"Histogram could not account for {source.mapping.column!r}"
            )
        heights = counts.astype(np.float64)
        if settings.normalization == Normalization.DENSITY and len(values):
            heights /= len(values) * widths
        if not np.isfinite(heights).all():
            raise ValueError(
                "Density overflowed; use Count normalization for this range"
            )
        counts.flags.writeable = heights.flags.writeable = False
        summaries.append(
            SeriesSummary(
                source.origin,
                source.mapping.label or source.filename,
                source.mapping.color,
                counts,
                heights,
                len(original),
                len(values),
                stats.nulls,
                stats.nonfinites,
                stats.uniques,
                statistics=stats,
            )
        )
    note = (
        "Exact finite-value counts; nulls and nonfinite values excluded. "
        "Common bins use (lower, upper], including the global minimum. "
        "Bins use Float64; integer statistics retain original extrema."
    )
    if scale != 1:
        note += f" Values are divided by {scale:.6g}; density is per displayed unit."
    if not all(math.isfinite(e) for e in edges):
        raise ValueError("The mapped numeric range cannot be represented")
    return PreparedComparison(
        settings, ColumnRole.NUMERIC, tuple(summaries), edges, scale, note=note
    )
