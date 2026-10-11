"""SparseProjectionAlgorithm: parameter ownership, fitting and input constraints."""

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import (
    EmbeddingEstimator,
    FittedDecompositionAlgorithm,
)
from datelier.analysis.embedding_parameters import SparseProjectionParameters
from datelier.analysis.types import PreparedInput


class SparseProjectionAlgorithm(
    FittedDecompositionAlgorithm[SparseProjectionParameters]
):
    parameter_type = SparseProjectionParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.random_projection import SparseRandomProjection

        request = prepared.request
        values = prepared.values
        params = self.parameters
        dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        estimator = SparseRandomProjection(
            n_components=dims,
            density=params.density,
            dense_output=True,
            random_state=seed,
        )
        return (estimator, values, tuple(details))
