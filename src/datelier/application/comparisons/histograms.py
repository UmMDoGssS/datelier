"""Prepared scalar histogram buffers shared by image and audio comparisons."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class HistogramSeries:
    identity: str
    label: str
    x: NDArray[np.float64]
    y: NDArray[np.float64]


@dataclass(frozen=True)
class HistogramPlot:
    xlabel: str
    ylabel: str
    series: tuple[HistogramSeries, ...]
    selected: str
    stamp: tuple[object, ...]
    note: str = ""
