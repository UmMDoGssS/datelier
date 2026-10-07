"""Worker-prepared scalar chart buffers beside complete exact profile tables."""

from dataclasses import dataclass
from threading import Event

import numpy as np
from numpy.typing import NDArray

from datelier.core.dataset import Dataset
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.text.corpus import TextProgress
from datelier.inspection.text.statistics import (
    TextProfile,
    calculate_profile,
    length_histogram,
)
from datelier.inspection.text.types import TextSettings


@dataclass(frozen=True)
class PreparedTextProfile:
    profile: TextProfile
    length_centers: NDArray[np.float64]
    length_counts: NDArray[np.float64]
    length_width: float
    frequency_positions: NDArray[np.float64]
    frequency_labels: tuple[str, ...]
    frequency_tokens: NDArray[np.float64]
    frequency_documents: NDArray[np.float64]

    @property
    def retained_bytes(self) -> int:
        return (
            int(self.profile.records.estimated_size())
            + int(self.profile.frequencies.estimated_size())
            + sum(
                a.nbytes
                for a in (
                    self.length_centers,
                    self.length_counts,
                    self.frequency_positions,
                    self.frequency_tokens,
                    self.frequency_documents,
                )
            )
        )


def prepare_profile(
    dataset: Dataset,
    file_id: str,
    settings: TextSettings,
    selection: tuple[int, ...],
    references: ReferenceSettings,
    index: ReferenceIndex | None,
    stop: Event,
    progress: TextProgress,
) -> PreparedTextProfile:
    profile = calculate_profile(
        dataset, file_id, settings, selection, references, index, stop, progress
    )
    counts, edges = length_histogram(profile, settings.profile_bins)
    top = profile.frequencies.head(12)
    return PreparedTextProfile(
        profile,
        (edges[1:] + edges[:-1]) / 2,
        counts,
        float(edges[1] - edges[0]),
        np.arange(top.height, dtype=np.float64),
        tuple(repr(piece[:60]) for piece in top["piece"]),
        top["tokens"].to_numpy().astype(np.float64),
        top["documents"].to_numpy().astype(np.float64),
    )
