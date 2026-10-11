"""IsomapAlgorithm: parameter ownership, fitting and input constraints."""

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import (
    EmbeddingEstimator,
    FittedDecompositionAlgorithm,
)
from datelier.analysis.embedding_parameters import IsomapParameters
from datelier.analysis.types import AnalysisRequest, PreparedInput


class IsomapAlgorithm(FittedDecompositionAlgorithm[IsomapParameters]):
    parameter_type = IsomapParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.manifold import Isomap

        request = prepared.request
        values = prepared.values
        params = self.parameters
        dims, _seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        estimator = Isomap(
            n_neighbors=params.neighbors,
            n_components=dims,
            metric=params.metric,
            eigen_solver="dense",
            path_method="D",
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
        if params.neighbors >= rows:
            raise ValueError("Neighbors must be smaller than the sampled row count")
