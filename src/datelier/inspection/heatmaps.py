"""Bounded scalar normalization and shared display-only linear color ramps."""

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray


class Colormap(StrEnum):
    GRAY = "Gray"
    BLUE_RED = "Blue–white–red"
    BLUE_YELLOW = "Blue–green–yellow"
    PURPLE_GOLD = "Purple–gold"


RAMPS: dict[Colormap, tuple[tuple[float, float, float], ...]] = {
    Colormap.GRAY: ((0, 0, 0), (1, 1, 1)),
    Colormap.BLUE_RED: ((0.15, 0.3, 0.8), (0.95, 0.95, 0.95), (0.8, 0.15, 0.15)),
    Colormap.BLUE_YELLOW: ((0.1, 0.15, 0.5), (0.1, 0.65, 0.45), (1, 0.9, 0.15)),
    Colormap.PURPLE_GOLD: ((0.3, 0.1, 0.5), (0.75, 0.3, 0.45), (1, 0.85, 0.2)),
}


def validate_range(bounds: tuple[float, float] | None) -> None:
    if bounds is not None:
        lo, hi = bounds
        if not np.isfinite(lo) or not np.isfinite(hi) or lo >= hi:
            raise ValueError("Display range needs finite, increasing endpoints")


@dataclass(frozen=True)
class NormalizedValues:
    colors: NDArray[np.float64]
    bounds: tuple[int | float, int | float] | None
    display_range: tuple[int | float, int | float] | None
    nonfinite: int


def normalize(
    raw: NDArray[np.generic], bounds: tuple[float, float] | None = None
) -> NormalizedValues:
    """Preserve integer bounds and float extremes; exclude nonfinite values."""
    validate_range(bounds)
    finite = np.isfinite(raw)
    values = raw[finite]
    original = (values.min().item(), values.max().item()) if values.size else None
    used = bounds if bounds is not None else original
    colors = np.full(raw.shape, np.nan, dtype=np.float64)
    if used is not None and values.size:
        lo, hi = (np.longdouble(value) for value in used)
        if lo == hi:
            colors[finite] = 0.5
        else:
            colors[finite] = np.asarray(
                np.clip((values.astype(np.longdouble) - lo) / (hi - lo), 0, 1),
                dtype=np.float64,
            )
    colors.flags.writeable = False
    return NormalizedValues(colors, original, used, int(raw.size - values.size))


def ramp_colors(colors: NDArray[np.float64], colormap: Colormap) -> NDArray[np.uint8]:
    """Linear ramps; nonfinite scalars use opaque magenta independently of range."""
    stops = np.asarray(RAMPS[colormap], dtype=np.float64)
    positions = np.linspace(0, 1, len(stops))
    finite = np.isfinite(colors)
    values = np.nan_to_num(colors, nan=0.0)
    rgba = np.full((*colors.shape, 4), 255, dtype=np.uint8)
    for channel in range(3):
        rgba[..., channel] = np.rint(
            np.interp(values, positions, stops[:, channel]) * 255
        ).astype(np.uint8)
    rgba[~finite] = (255, 0, 255, 255)
    rgba.flags.writeable = False
    return rgba
