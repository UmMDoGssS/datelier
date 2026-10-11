"SVDAlgorithm: parameter ownership, fitting and input constraints."

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import (
    EmbeddingEstimator,
    FittedDecompositionAlgorithm,
)
from datelier.analysis.parameter_fields import setting

if TYPE_CHECKING:
    from datelier.analysis.types import AnalysisRequest, PreparedInput


@dataclass(frozen=True)
class SVDParameters:
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.SVD
    iterations: int = setting(5, "Power iterations", 1, 100)


class SVDAlgorithm(FittedDecompositionAlgorithm[SVDParameters]):
    parameter_type = SVDParameters
    row_limit = 100000
    default_row_limit = 10000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.decomposition import TruncatedSVD

        request = prepared.request
        values = prepared.values
        params = self.parameters
        dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        estimator = TruncatedSVD(
            n_components=dims, n_iter=params.iterations, random_state=seed
        )
        return (estimator, values, tuple(details))

    def diagnostics(self, estimator: EmbeddingEstimator) -> tuple[tuple[str, str], ...]:
        from sklearn.decomposition import TruncatedSVD

        estimator = cast(TruncatedSVD, estimator)
        details: list[tuple[str, str]] = []
        details.append(
            (
                "Explained variance ratio",
                str(estimator.explained_variance_ratio_.tolist()),
            )
        )
        return tuple(details)

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        rows, width = values.shape
        if request.dimensions > min(rows, width):
            raise ValueError(
                "Output dimensions exceed sampled rows or varying feature count"
            )
        if width < 2:
            raise ValueError("Truncated SVD needs at least two varying features")
