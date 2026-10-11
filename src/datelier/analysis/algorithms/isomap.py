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
class IsomapAlgorithm(FittedDecompositionAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.ISOMAP
    neighbors: int = setting(15, "Neighbors", 2, 100)
    metric: str = choice("euclidean", "Distance", ("euclidean", "manhattan"))
    recipe_kind: ClassVar[str] = "IsomapParameters"
    row_limit: ClassVar[int] = 3000
    default_row_limit: ClassVar[int] = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.manifold import Isomap

        request = prepared.request
        values = prepared.values
        dims, _seed = (request.dimensions, request.seed)
        estimator = Isomap(
            n_neighbors=self.neighbors,
            n_components=dims,
            metric=self.metric,
            eigen_solver="dense",
            path_method="D",
            n_jobs=1,
        )
        return (estimator, values, ())

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        rows, width = values.shape
        if rows <= request.dimensions + 1:
            raise ValueError(
                "Manifold views need more sampled rows than dimensions + 1"
            )
        if self.neighbors >= rows:
            raise ValueError("Neighbors must be smaller than the sampled row count")


# Legacy recipe/import name refers to this same algorithm, not a second record.
IsomapParameters = IsomapAlgorithm
