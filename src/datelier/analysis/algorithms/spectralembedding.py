"""SpectralEmbeddingAlgorithm: parameter ownership, fitting and input constraints."""

from typing import Literal, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import (
    EmbeddingEstimator,
    FittedDecompositionAlgorithm,
)
from datelier.analysis.embedding_parameters import SpectralEmbeddingParameters
from datelier.analysis.types import AnalysisRequest, PreparedInput


class SpectralEmbeddingAlgorithm(
    FittedDecompositionAlgorithm[SpectralEmbeddingParameters]
):
    parameter_type = SpectralEmbeddingParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.manifold import SpectralEmbedding

        request = prepared.request
        values = prepared.values
        params = self.parameters
        dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        estimator = SpectralEmbedding(
            n_components=dims,
            affinity=cast(Literal["nearest_neighbors", "rbf"], params.affinity),
            n_neighbors=params.neighbors
            if params.affinity == "nearest_neighbors"
            else None,
            gamma=params.gamma if params.affinity == "rbf" else None,
            eigen_solver="arpack",
            random_state=seed,
            n_jobs=1,
        )
        return (estimator, values, tuple(details))

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        params = self.parameters
        rows, width = values.shape
        if rows <= request.dimensions + 1:
            raise ValueError(
                "Manifold views need more sampled rows than dimensions + 1"
            )
        uses_neighbors = params.affinity == "nearest_neighbors"
        if uses_neighbors and params.neighbors >= rows:
            raise ValueError("Neighbors must be smaller than the sampled row count")
