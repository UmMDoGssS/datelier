"""IsomapAlgorithm: parameter ownership, fitting and input constraints."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import (
    EmbeddingEstimator,
    FittedDecompositionAlgorithm,
)
from datelier.analysis.parameter_fields import choice, setting

if TYPE_CHECKING:
    from datelier.analysis.types import AnalysisRequest, PreparedInput


@dataclass(frozen=True)
class IsomapParameters:
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.ISOMAP
    neighbors: int = setting(15, "Neighbors", 2, 100)
    metric: str = choice("euclidean", "Distance", ("euclidean", "manhattan"))


class IsomapAlgorithm(FittedDecompositionAlgorithm[IsomapParameters]):
    parameter_type = IsomapParameters
    row_limit = 3000
    default_row_limit = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.manifold import Isomap

        request = prepared.request
        values = prepared.values
        params = self.parameters
        dims, _seed = (request.dimensions, request.seed)
        estimator = Isomap(
            n_neighbors=params.neighbors,
            n_components=dims,
            metric=params.metric,
            eigen_solver="dense",
            path_method="D",
            n_jobs=1,
        )
        return estimator, values, ()

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
