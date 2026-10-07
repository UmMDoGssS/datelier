"""Streaming channel moments and numerically stable histogram coordinates."""

from typing import cast

import numpy as np
from numpy.typing import NDArray

from datelier.inspection.images.profile_types import (
    ChannelKey,
    ChannelSummary,
    ImageHistogram,
)


class ChannelMoments:
    def __init__(self) -> None:
        self.values = self.finite = 0
        self.minimum: int | float | None = None
        self.maximum: int | float | None = None
        self.mean = np.longdouble(0)
        self.m2 = np.longdouble(0)

    def add(self, values: NDArray[np.generic]) -> None:
        self.values += values.size
        chosen = values[np.isfinite(values)]
        count = chosen.size
        if not count:
            return
        lo, hi = (
            cast(int | float, chosen.min().item()),
            cast(int | float, chosen.max().item()),
        )
        self.minimum = lo if self.minimum is None else min(self.minimum, lo)
        self.maximum = hi if self.maximum is None else max(self.maximum, hi)
        extended = np.asarray(chosen, dtype=np.longdouble)
        mean = extended.mean(dtype=np.longdouble)
        m2 = np.sum((extended - mean) ** 2, dtype=np.longdouble)
        self._merge(count, mean, m2)

    def _merge(self, count: int, mean: np.longdouble, m2: np.longdouble) -> None:
        total = self.finite + count
        delta = mean - self.mean
        self.m2 += m2 + delta * delta * (np.longdouble(self.finite) * count / total)
        self.mean += delta * (np.longdouble(count) / total)
        self.finite = total

    def merge(self, other: ChannelMoments) -> None:
        self.values += other.values
        if not other.finite:
            return
        assert other.minimum is not None and other.maximum is not None
        self.minimum = (
            other.minimum if self.minimum is None else min(self.minimum, other.minimum)
        )
        self.maximum = (
            other.maximum if self.maximum is None else max(self.maximum, other.maximum)
        )
        self._merge(other.finite, other.mean, other.m2)

    def summary(self, key: ChannelKey) -> ChannelSummary:
        return ChannelSummary(
            key,
            self.values,
            self.finite,
            self.values - self.finite,
            self.minimum,
            self.maximum,
            float(self.mean) if self.finite else None,
            float(np.sqrt(max(np.longdouble(0), self.m2) / self.finite))
            if self.finite
            else None,
        )


def normalized_values(
    values: NDArray[np.generic],
    minimum: int | float,
    maximum: int | float,
) -> NDArray[np.longdouble]:
    chosen = np.asarray(values[np.isfinite(values)], dtype=np.longdouble)
    if minimum == maximum:
        return np.full(chosen.shape, 0.5, dtype=np.longdouble)
    lo, hi = np.longdouble(minimum), np.longdouble(maximum)
    return np.clip((chosen - lo) / (hi - lo), 0, 1)


def histogram(
    label: str,
    counts: NDArray[np.float64],
    minimum: int | float | None,
    maximum: int | float | None,
) -> ImageHistogram:
    normalized = np.linspace(0, 1, len(counts) + 1, dtype=np.float64)
    if minimum is None or maximum is None:
        return ImageHistogram(label, normalized, counts)
    lo, hi = np.longdouble(minimum), np.longdouble(maximum)
    if minimum == maximum:
        lo, hi = lo - 0.5, hi + 0.5
    physical = np.asarray(
        lo + (hi - lo) * normalized.astype(np.longdouble), dtype=np.float64
    )
    scaled = not np.isfinite(physical).all() or not np.all(np.diff(physical) > 0)
    return ImageHistogram(
        label, normalized if scaled else physical, counts, scaled, minimum, maximum
    )
