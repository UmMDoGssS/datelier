"""Worker-side playback-only PCM conversion; original samples remain untouched."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class PlaybackSamples:
    values: NDArray[np.float64]
    nonfinite: int
    description: str


def output_samples(raw: NDArray[np.generic]) -> PlaybackSamples:
    if raw.ndim != 2 or raw.dtype.kind not in "iuf":
        raise ValueError("Playback requires real sample-frame/channel values")
    with np.errstate(over="ignore"):
        values = np.array(raw, dtype=np.float64, copy=True)
    if np.any(np.isfinite(raw) & ~np.isfinite(values)):
        raise ValueError("Original amplitude exceeds Float64 playback conversion")
    nonfinite = int(np.count_nonzero(~np.isfinite(values)))
    values[~np.isfinite(values)] = 0
    if raw.dtype.kind in "iu":
        bits = raw.dtype.itemsize * 8
        rail = float(2 ** (bits - 1))
        if raw.dtype.kind == "u":
            values -= rail
        values /= rail
        description = f"Original {raw.dtype} PCM rails mapped to ±1" + (
            " with unsigned midpoint at zero" if raw.dtype.kind == "u" else ""
        )
    else:
        description = "Original floating amplitude; no automatic normalization"
    values.flags.writeable = False
    return PlaybackSamples(values, nonfinite, description)
