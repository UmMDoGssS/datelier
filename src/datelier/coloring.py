"""Prepared per-point colors aligned to bounded displayed source rows."""

from dataclasses import dataclass

import numpy as np
import polars as pl
from numpy.typing import NDArray

from datelier.dataset import Dataset
from datelier.profiling import COUNT_ROW_LIMIT, ProfileKind, profile_kind

NEUTRAL = 0xFF888888
PALETTE = (
    0xFFE5A04C,
    0xFF5599F2,
    0xFF77C478,
    0xFFC976BB,
    0xFF65CFDD,
    0xFFCF9D87,
    0xFF8E85E6,
    0xFF91CACA,
    0xFFB4A766,
    0xFFBE7299,
    0xFFCECC83,
    0xFF839DD1,
)


@dataclass(frozen=True)
class PointColors:
    name: str
    rgba: NDArray[np.uint32]
    legend: tuple[tuple[str, int], ...]
    note: str


def continuous_colors(values: NDArray[np.float64], name: str) -> PointColors:
    mask = np.isfinite(values)
    rgba = np.full(len(values), NEUTRAL, dtype=np.uint32)
    legend: tuple[tuple[str, int], ...] = ()
    if mask.any():
        lo, hi = float(values[mask].min()), float(values[mask].max())
        scale = max(abs(lo), abs(hi)) or 1
        low, high = lo / scale, hi / scale
        t = (
            (values[mask] / scale - low) / (high - low)
            if hi > lo
            else np.full(mask.sum(), 0.5)
        )
        red = (50 + 195 * t).astype(np.uint32)
        blue = (245 - 195 * t).astype(np.uint32)
        rgba[mask] = red | (np.uint32(100) << 8) | (blue << 16) | np.uint32(0xFF000000)
        legend = ((f"{lo:.6g}", 0xFFF56432), (f"{hi:.6g}", 0xFF3264F5))
    rgba.flags.writeable = False
    return PointColors(
        name,
        rgba,
        (*legend, ("Missing / nonfinite", NEUTRAL)),
        "Continuous scale uses displayed finite values.",
    )


def prepare_colors(
    dataset: Dataset, positions: NDArray[np.uint64], column: str
) -> PointColors:
    series = dataset.table.get_column(column)
    kind = profile_kind(series.dtype)
    if kind not in (ProfileKind.NUMERIC, ProfileKind.TEMPORAL, ProfileKind.CATEGORICAL):
        raise ValueError(
            "Color requires numeric, temporal, categorical or Boolean data"
        )
    shown = series.gather(positions).rename("value")
    minimum: object = None
    if kind == ProfileKind.TEMPORAL:
        physical = shown.to_physical().cast(pl.Int128)
        minimum = physical.min()
        # Shift before Float64 conversion to preserve nanosecond differences.
        shown = (
            physical.to_frame()
            .select(
                pl.col("value")
                - pl.lit(minimum if isinstance(minimum, int) else 0, dtype=pl.Int128)
            )
            .to_series()
        )
    if kind in (ProfileKind.NUMERIC, ProfileKind.TEMPORAL):
        result = continuous_colors(shown.cast(pl.Float64).to_numpy(), column)
        if kind == ProfileKind.TEMPORAL:
            return PointColors(
                column,
                result.rgba,
                result.legend,
                f"Physical units relative to {minimum}; " + result.note,
            )
        return result
    counts = (
        series.head(COUNT_ROW_LIMIT)
        .cast(pl.String)
        .rename("value")
        .drop_nulls()
        .value_counts()
    )
    top = (
        counts.sort(["count", "value"], descending=[True, False])
        .head(12)["value"]
        .to_list()
    )
    lookup = {value: PALETTE[i] for i, value in enumerate(top)}
    other = 0xFFBBBBBB
    rgba = np.array(
        [
            NEUTRAL if v is None else lookup.get(v, other)
            for v in shown.cast(pl.String).to_list()
        ],
        dtype=np.uint32,
    )
    rgba.flags.writeable = False
    legend = tuple((str(v)[:120], lookup[v]) for v in top)
    return PointColors(
        column,
        rgba,
        (*legend, ("Other", other), ("Missing", NEUTRAL)),
        "Top 12 categories from at most 100,000 input rows; "
        "remaining values are Other.",
    )
