"""KernelPCAAlgorithm: parameter ownership, fitting and input constraints."""

from typing import Literal, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import (
    EmbeddingEstimator,
    FittedDecompositionAlgorithm,
)
from datelier.analysis.embedding_parameters import KernelPCAParameters
from datelier.analysis.types import AnalysisRequest, PreparedInput


class KernelPCAAlgorithm(FittedDecompositionAlgorithm[KernelPCAParameters]):
    parameter_type = KernelPCAParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.decomposition import KernelPCA

        request = prepared.request
        values = prepared.values
        params = self.parameters
        dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        estimator = KernelPCA(
            n_components=dims,
            kernel=cast(Literal["rbf", "poly", "cosine", "linear"], params.kernel),
            gamma=params.gamma if params.kernel in ("rbf", "poly") else None,
            degree=params.degree if params.kernel == "poly" else 3,
            eigen_solver="arpack",
            random_state=seed,
            n_jobs=1,
        )
        return (estimator, values, tuple(details))

    def diagnostics(self, estimator: EmbeddingEstimator) -> tuple[tuple[str, str], ...]:
        from sklearn.decomposition import KernelPCA

        estimator = cast(KernelPCA, estimator)
        details: list[tuple[str, str]] = []
        details.append(("Eigenvalues", str(estimator.eigenvalues_.tolist())))
        return tuple(details)

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        rows, width = values.shape
        if rows <= request.dimensions:
            raise ValueError(
                "Kernel PCA needs more sampled rows than output dimensions"
            )
