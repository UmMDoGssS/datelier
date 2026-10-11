"""Sparse HTK mel triangles integrate original one-sided density into band power."""

from dataclasses import dataclass
from math import expm1, log, log1p

import numpy as np
from numpy.typing import NDArray


def hz_to_mel(frequency: float) -> float:
    return 2595 / log(10) * log1p(frequency / 700)


def mel_to_hz(value: float) -> float:
    return 700 * expm1(value * log(10) / 2595)


@dataclass(frozen=True)
class MelBank:
    centers: NDArray[np.float64]
    edges: NDArray[np.float64]
    bins: NDArray[np.int64]
    bands: NDArray[np.int64]
    weights: NDArray[np.float64]
    bounds: tuple[float, float]  # Uniform mel raster coordinates.
    empty: int
    bin_width: float

    def apply(self, density: NDArray[np.float64]) -> NDArray[np.float64]:
        return np.bincount(
            self.bands,
            weights=density[self.bins] * self.weights * self.bin_width,
            minlength=len(self.centers),
        )


def mel_filters(rate: int, fft: int, count: int, low: float, high: float) -> MelBank:
    """Unit-height triangles in Hz, equally spaced on the HTK mel scale.

    PSD × FFT-bin Hz width yields original amplitude units² per band. This is
    neither area-normalized filter density nor arbitrary FFT magnitude power.
    Sparse supports avoid count × FFT allocation. Empty supports remain visible.
    """
    if rate <= 0 or fft < 2 or count < 1 or not 0 <= low < high <= rate / 2:
        raise ValueError("Mel filters require an available original-frequency range")
    points = np.linspace(hz_to_mel(low), hz_to_mel(high), count + 2)
    edges = np.array([mel_to_hz(float(value)) for value in points])
    edges[0], edges[-1] = low, high
    frequencies = np.fft.rfftfreq(fft, 1 / rate)
    bins: list[NDArray[np.int64]] = []
    bands: list[NDArray[np.int64]] = []
    weights: list[NDArray[np.float64]] = []
    empty = 0
    for band in range(count):
        first, center, last = edges[band : band + 3]
        start = np.searchsorted(frequencies, first, side="right")
        stop = np.searchsorted(frequencies, last, side="left")
        chosen = np.arange(start, stop, dtype=np.int64)
        coefficients = np.minimum(
            (frequencies[chosen] - first) / (center - first),
            (last - frequencies[chosen]) / (last - center),
        )
        bins.append(chosen)
        bands.append(np.full(len(chosen), band, dtype=np.int64))
        weights.append(coefficients)
        empty += int(len(chosen) == 0)
    centers = edges[1:-1].copy()
    indices, labels, coefficients = (
        np.concatenate(bins),
        np.concatenate(bands),
        np.concatenate(weights),
    )
    for array in (centers, edges, indices, labels, coefficients):
        array.flags.writeable = False
    spacing = (points[-1] - points[0]) / (count + 1)
    return MelBank(
        centers,
        edges,
        indices,
        labels,
        coefficients,
        (float(points[0] + spacing / 2), float(points[-1] - spacing / 2)),
        empty,
        rate / fft,
    )
