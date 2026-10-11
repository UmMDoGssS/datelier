"""Immutable source inputs and finite scalar comparisons with compatible units."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from datelier.core import Dataset
from datelier.inspection.arrays import ArrayCatalog, ArrayRecordMapping
from datelier.inspection.audio.collections import AudioCollectionProfile
from datelier.inspection.audio.comparisons.settings import (
    AudioComparisonSettings,
    AudioComparisonSource,
)
from datelier.inspection.references import ReferenceSettings
from datelier.inspection.references.index import ReferenceIndex
from datelier.io.arrays import ArrayStore


@dataclass(frozen=True)
class AudioComparisonInput:
    source: AudioComparisonSource
    dataset: Dataset
    label: str
    view_name: str = ""
    references: ReferenceSettings = ReferenceSettings()
    index: ReferenceIndex | None = None
    selection: tuple[int, ...] = ()
    arrays: ArrayStore | None = None
    catalog: ArrayCatalog | None = None
    mapping: ArrayRecordMapping | None = None


@dataclass(frozen=True)
class AudioMetric:
    name: str
    field: str
    family: str
    channel: int | None = None

    @property
    def label(self) -> str:
        suffix = f" · channel {self.channel + 1}" if self.channel is not None else ""
        return f"{self.name} · {self.family}{suffix}"


@dataclass(frozen=True)
class AudioScalarSummary:
    values: int
    minimum: float | None
    maximum: float | None
    mean: float | None


@dataclass(frozen=True)
class AudioComparisonCurve:
    metric: AudioMetric
    minimum: float | None
    maximum: float | None
    scaled: bool
    edges: NDArray[np.float64]
    plot_x: NDArray[np.float64]
    counts: tuple[NDArray[np.float64] | None, ...]
    proportions: tuple[NDArray[np.float64] | None, ...]
    summaries: tuple[AudioScalarSummary | None, ...]

    @property
    def retained_bytes(self) -> int:
        return (
            self.edges.nbytes
            + self.plot_x.nbytes
            + sum(a.nbytes for a in (*self.counts, *self.proportions) if a is not None)
        )


@dataclass(frozen=True)
class PreparedAudioComparison:
    settings: AudioComparisonSettings
    labels: tuple[str, ...]
    profiles: tuple[AudioCollectionProfile, ...]
    curves: tuple[AudioComparisonCurve, ...]

    @property
    def retained_bytes(self) -> int:
        return sum(p.retained_bytes for p in self.profiles) + sum(
            c.retained_bytes for c in self.curves
        )
