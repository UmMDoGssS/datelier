"""Immutable command inputs and aligned common-bin comparison series."""

from dataclasses import dataclass

from datelier.core import Dataset
from datelier.inspection.arrays import ArrayCatalog, ArrayRecordMapping
from datelier.inspection.images.comparisons.settings import (
    ImageComparisonSettings,
    ImageComparisonSource,
)
from datelier.inspection.images.profiles import (
    ChannelKey,
    ImageBounds,
    ImageHistogram,
    ImageProfile,
)
from datelier.inspection.references import ReferenceSettings
from datelier.inspection.references.index import ReferenceIndex
from datelier.io.arrays import ArrayStore


@dataclass(frozen=True)
class ImageComparisonInput:
    source: ImageComparisonSource
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
class ImageComparisonCurve:
    key: ChannelKey
    counts: tuple[ImageHistogram | None, ...]
    proportions: tuple[ImageHistogram | None, ...]


@dataclass(frozen=True)
class PreparedImageComparison:
    settings: ImageComparisonSettings
    labels: tuple[str, ...]
    profiles: tuple[ImageProfile, ...]
    bounds: ImageBounds
    curves: tuple[ImageComparisonCurve, ...]

    @property
    def retained_bytes(self) -> int:
        return sum(profile.retained_bytes for profile in self.profiles) + sum(
            chart.counts.nbytes
            + (chart.plot_counts.nbytes if chart.plot_counts is not None else 0)
            for curve in self.curves
            for chart in curve.proportions
            if chart is not None
        )
