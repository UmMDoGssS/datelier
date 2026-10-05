"""Validate finite, row-aligned coordinates and retain fit provenance."""

import numpy as np
from numpy.typing import NDArray

from datelier.analysis_provenance import make_provenance
from datelier.analysis_types import EmbeddingResult, PreparedInput


def embedding_result(
    prepared: PreparedInput,
    coordinates: NDArray[np.float64],
    started: float,
    details: tuple[tuple[str, str], ...],
    libraries: tuple[str, ...] = ("numpy", "polars", "scikit-learn", "threadpoolctl"),
) -> EmbeddingResult:
    if (
        coordinates.shape != (len(prepared.row_ids), prepared.request.dimensions)
        or not np.isfinite(coordinates).all()
    ):
        raise ValueError("Analysis produced invalid coordinates")
    coordinates.flags.writeable = False
    return EmbeddingResult(
        prepared.revision,
        prepared.row_ids,
        prepared.positions,
        coordinates,
        make_provenance(prepared, started, libraries),
        details,
    )
