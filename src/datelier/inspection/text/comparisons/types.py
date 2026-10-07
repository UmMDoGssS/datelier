"""Worker inputs and complete exact comparison buffers with file provenance."""

from dataclasses import dataclass

import numpy as np
import polars as pl
from numpy.typing import NDArray

from datelier.core.dataset import Dataset
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.text.comparisons.settings import (
    TextComparisonSettings,
    TextComparisonSource,
)
from datelier.inspection.text.statistics import TextProfile


@dataclass(frozen=True)
class TextComparisonInput:
    source: TextComparisonSource
    dataset: Dataset
    label: str
    references: ReferenceSettings = ReferenceSettings()
    index: ReferenceIndex | None = None
    selection: tuple[int, ...] = ()


@dataclass(frozen=True)
class PreparedTextComparison:
    settings: TextComparisonSettings
    labels: tuple[str, ...]
    profiles: tuple[TextProfile, ...]
    edges: NDArray[np.float64]
    centers: NDArray[np.float64]
    lengths: tuple[NDArray[np.float64], ...]
    frequencies: pl.DataFrame
    frequency_labels: tuple[str, ...]
    frequency_positions: NDArray[np.float64]
    frequency_series_positions: tuple[NDArray[np.float64], ...]
    token_frequencies: tuple[NDArray[np.float64], ...]
    document_frequencies: tuple[NDArray[np.float64], ...]

    @property
    def retained_bytes(self) -> int:
        return (
            int(self.frequencies.estimated_size())
            + sum(
                int(p.records.estimated_size()) + int(p.frequencies.estimated_size())
                for p in self.profiles
            )
            + sum(
                a.nbytes
                for a in (
                    self.edges,
                    self.centers,
                    self.frequency_positions,
                    *self.lengths,
                    *self.frequency_series_positions,
                    *self.token_frequencies,
                    *self.document_frequencies,
                )
            )
        )
