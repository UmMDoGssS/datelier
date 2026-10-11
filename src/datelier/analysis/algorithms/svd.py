"""SVDAlgorithm: parameter ownership, fitting and input constraints."""

from typing import cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import (
    EmbeddingEstimator,
    FittedDecompositionAlgorithm,
)
from datelier.analysis.embedding_parameters import SVDParameters
from datelier.analysis.types import AnalysisRequest, PreparedInput


class SVDAlgorithm(FittedDecompositionAlgorithm[SVDParameters]):
    parameter_type = SVDParameters

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
