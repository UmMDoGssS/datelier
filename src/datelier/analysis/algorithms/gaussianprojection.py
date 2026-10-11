"GaussianProjectionAlgorithm: parameter ownership, fitting and input constraints."

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import (
    EmbeddingEstimator,
    FittedDecompositionAlgorithm,
)

if TYPE_CHECKING:
    from datelier.analysis.types import PreparedInput


@dataclass(frozen=True)
class GaussianProjectionParameters:
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.GAUSSIAN_PROJECTION


class GaussianProjectionAlgorithm(
    FittedDecompositionAlgorithm[GaussianProjectionParameters]
):
    parameter_type = GaussianProjectionParameters
    row_limit = 100000
    default_row_limit = 10000

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
