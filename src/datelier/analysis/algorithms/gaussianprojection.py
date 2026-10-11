"""GaussianProjectionAlgorithm: parameter ownership, fitting and input constraints."""

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import (
    EmbeddingEstimator,
    FittedDecompositionAlgorithm,
)
from datelier.analysis.embedding_parameters import GaussianProjectionParameters
from datelier.analysis.types import PreparedInput


class GaussianProjectionAlgorithm(
    FittedDecompositionAlgorithm[GaussianProjectionParameters]
):
    parameter_type = GaussianProjectionParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.random_projection import GaussianRandomProjection

        request = prepared.request
        values = prepared.values
        dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        estimator = GaussianRandomProjection(n_components=dims, random_state=seed)
        return (estimator, values, tuple(details))
