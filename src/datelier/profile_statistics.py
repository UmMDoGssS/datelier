"""Exact numeric summaries prepared in workers, in original column units."""

import math
from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True)
class NumericStatistics:
    nonnull: int
    uniques: int
    finite: int
    nulls: int
    nans: int
    nonfinites: int
    mean: float | None = None
    std: float | None = None
    minimum: int | float | None = None
    q25: float | None = None
    median: float | None = None
    q75: float | None = None
    maximum: int | float | None = None
    mode: int | float | None = None
    mode_count: int = 0
    mode_ties: int = 0
    rounded_mode: bool = False


def _number(value: object) -> float | None:
    return (
        float(value)
        if isinstance(value, (int, float)) and math.isfinite(value)
        else None
    )


def prepare_numeric_statistics(
    series: pl.Series, *, uniques: int | None = None
) -> NumericStatistics:
    series = series.rename("value")
    values = series.cast(pl.Float64)
    finite = values.filter(values.is_finite())
    nonnull = len(series) - series.null_count()
    quality = dict(
        nonnull=nonnull,
        uniques=uniques if uniques is not None else series.drop_nulls().n_unique(),
        finite=len(finite),
        nulls=series.null_count(),
        nans=int(values.is_nan().sum()),
        nonfinites=nonnull - len(finite),
        rounded_mode=not series.dtype.is_integer(),
    )
    if not len(finite):
        return NumericStatistics(**quality)
    minimum, maximum = _number(finite.min()), _number(finite.max())
    assert minimum is not None and maximum is not None
    scale = max(abs(minimum), abs(maximum)) or 1.0
    normalized = finite / scale
    mean = _number(normalized.mean())
    std = _number(normalized.std(ddof=1))
    # Normalized interpolation avoids overflow when finite extrema have an
    # infinite difference. Clamp rounding error at the representable extrema.
    quantiles = []
    for q in (0.25, 0.5, 0.75):
        value = _number(normalized.quantile(q, interpolation="linear"))
        quantiles.append(max(minimum, min(maximum, value * scale)) if value else 0.0)
    mode_values = (
        series.filter(values.is_finite())
        if series.dtype.is_integer()
        else finite.rename("value")
        .to_frame()
        .select(
            # At large magnitudes cents are below Float64 precision; rounding
            # by multiplying by 100 can overflow otherwise finite values.
            pl.when(pl.col("value").abs() < 1e14)
            .then(pl.col("value").round(2))
            .otherwise(pl.col("value"))
        )
        .to_series()
    )
    counts = mode_values.rename("value").value_counts()
    mode_count = counts.get_column("count").max()
    assert isinstance(mode_count, int)
    modes = counts.filter(pl.col("count") == mode_count)
    mode = modes.get_column("value").min()
    # Preserve integer extrema and mode, including integers above 2**53.
    original_finite = series.filter(values.is_finite())
    low, high = original_finite.min(), original_finite.max()
    return NumericStatistics(
        **quality,
        mean=_number(max(-1.0, min(1.0, mean)) * scale) if mean is not None else None,
        std=_number(std * scale) if std is not None else None,
        minimum=low if isinstance(low, (int, float)) else minimum,
        q25=quantiles[0],
        median=quantiles[1],
        q75=quantiles[2],
        maximum=high if isinstance(high, (int, float)) else maximum,
        mode=mode if isinstance(mode, (int, float)) else None,
        mode_count=mode_count,
        mode_ties=modes.height,
    )
