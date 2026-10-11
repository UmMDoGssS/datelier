"""ICAAlgorithm: parameter ownership, fitting and input constraints."""

from typing import Literal, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import (
    EmbeddingEstimator,
    FittedDecompositionAlgorithm,
)
from datelier.analysis.embedding_parameters import ICAParameters
from datelier.analysis.types import AnalysisRequest, PreparedInput


class ICAAlgorithm(FittedDecompositionAlgorithm[ICAParameters]):
    parameter_type = ICAParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.decomposition import FastICA

        request = prepared.request
        values = prepared.values
        params = self.parameters
        dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        estimator = FastICA(
            n_components=dims,
            fun=cast(Literal["logcosh", "exp", "cube"], params.function),
            max_iter=params.iterations,
            tol=params.tolerance,
            random_state=seed,
            whiten="unit-variance",
        )
        return (estimator, values, tuple(details))

    def diagnostics(self, estimator: EmbeddingEstimator) -> tuple[tuple[str, str], ...]:
        from sklearn.decomposition import FastICA

        estimator = cast(FastICA, estimator)
        details: list[tuple[str, str]] = []
        details.append(("Completed iterations", str(estimator.n_iter_)))
        return tuple(details)

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        rows, width = values.shape
        if request.dimensions > min(rows, width):
            raise ValueError(
                "Output dimensions exceed sampled rows or varying feature count"
            )
