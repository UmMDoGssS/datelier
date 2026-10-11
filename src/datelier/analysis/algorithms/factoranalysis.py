"""FactorAnalysisAlgorithm: parameter ownership, fitting and input constraints."""

from typing import Literal, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import (
    EmbeddingEstimator,
    FittedDecompositionAlgorithm,
)
from datelier.analysis.embedding_parameters import FactorAnalysisParameters
from datelier.analysis.types import AnalysisRequest, PreparedInput


class FactorAnalysisAlgorithm(FittedDecompositionAlgorithm[FactorAnalysisParameters]):
    parameter_type = FactorAnalysisParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.decomposition import FactorAnalysis

        request = prepared.request
        values = prepared.values
        params = self.parameters
        dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        rotation = (
            None
            if params.rotation == "none"
            else cast(Literal["varimax", "quartimax"], params.rotation)
        )
        estimator = FactorAnalysis(
            n_components=dims,
            rotation=rotation,
            max_iter=params.iterations,
            tol=params.tolerance,
            random_state=seed,
        )
        return (estimator, values, tuple(details))

    def diagnostics(self, estimator: EmbeddingEstimator) -> tuple[tuple[str, str], ...]:
        from sklearn.decomposition import FactorAnalysis

        estimator = cast(FactorAnalysis, estimator)
        details: list[tuple[str, str]] = []
        details.append(("Final log likelihood", f"{estimator.loglike_[-1]:.6g}"))
        return tuple(details)

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        rows, width = values.shape
        if request.dimensions > min(rows, width):
            raise ValueError(
                "Output dimensions exceed sampled rows or varying feature count"
            )
