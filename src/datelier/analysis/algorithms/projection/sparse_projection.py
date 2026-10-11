"""SparseProjectionAlgorithm: parameter ownership, fitting and input constraints."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import (
    DecompositionAlgorithm,
    EmbeddingEstimator,
)
from datelier.analysis.parameter_fields import setting

if TYPE_CHECKING:
    from datelier.analysis.types import PreparedInput


@dataclass(frozen=True)
class SparseProjectionAlgorithm(DecompositionAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.SPARSE_PROJECTION
    density: float = setting(0.3, "Projection density", 1e-06, 1.0)
    recipe_kind: ClassVar[str] = "SparseProjectionParameters"
    row_limit: ClassVar[int] = 100000
    default_row_limit: ClassVar[int] = 10000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.random_projection import SparseRandomProjection

        request = prepared.request
        values = prepared.values
        dims, seed = (request.dimensions, request.seed)
        estimator = SparseRandomProjection(
            n_components=dims,
            density=self.density,
            dense_output=True,
            random_state=seed,
        )
        return (estimator, values, ())
