"""GaussianProjectionAlgorithm: parameter ownership, fitting and input constraints."""

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
class GaussianProjectionAlgorithm(FittedDecompositionAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.GAUSSIAN_PROJECTION
    recipe_kind: ClassVar[str] = "GaussianProjectionParameters"
    row_limit: ClassVar[int] = 100000
    default_row_limit: ClassVar[int] = 10000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.random_projection import GaussianRandomProjection

        request = prepared.request
        values = prepared.values
        dims, seed = (request.dimensions, request.seed)
        estimator = GaussianRandomProjection(n_components=dims, random_state=seed)
        return (estimator, values, ())


# Legacy recipe/import name refers to this same algorithm, not a second record.
GaussianProjectionParameters = GaussianProjectionAlgorithm
