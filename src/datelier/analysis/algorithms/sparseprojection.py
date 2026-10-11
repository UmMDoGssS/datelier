"SparseProjectionAlgorithm: parameter ownership, fitting and input constraints."

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import (
    EmbeddingEstimator,
    FittedDecompositionAlgorithm,
)
from datelier.analysis.parameter_fields import setting

if TYPE_CHECKING:
    from datelier.analysis.types import PreparedInput


@dataclass(frozen=True)
class SparseProjectionParameters:
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.SPARSE_PROJECTION
    density: float = setting(0.3, "Projection density", 1e-6, 1.0)


class SparseProjectionAlgorithm(
    FittedDecompositionAlgorithm[SparseProjectionParameters]
):
    parameter_type = SparseProjectionParameters
    row_limit = 100000
    default_row_limit = 10000

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
