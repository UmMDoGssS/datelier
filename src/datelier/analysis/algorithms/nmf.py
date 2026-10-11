"""NMFAlgorithm: parameter ownership, fitting and input constraints."""

from typing import cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import (
    EmbeddingEstimator,
    FittedDecompositionAlgorithm,
)
from datelier.analysis.embedding_parameters import NMFParameters
from datelier.analysis.types import AnalysisRequest, PreparedInput


class NMFAlgorithm(FittedDecompositionAlgorithm[NMFParameters]):
    parameter_type = NMFParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.decomposition import NMF

        request = prepared.request
        values = prepared.values
        params = self.parameters
        dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        if params.scaling == "minmax":
            normalized = values / np.abs(values).max(axis=0)
            low, high = (normalized.min(axis=0), normalized.max(axis=0))
            values = (normalized - low) / (high - low)
            details.append(("NMF input", "Each fitted feature scaled to [0, 1]"))
        elif np.any(values < 0):
            raise ValueError(
                "NMF needs nonnegative inputs; choose minmax scaling "
                "or disable standardization on nonnegative data"
            )
        estimator = NMF(
            n_components=dims,
            init="nndsvda",
            max_iter=params.iterations,
            tol=params.tolerance,
            random_state=seed,
        )
        return (estimator, values, tuple(details))

    def diagnostics(self, estimator: EmbeddingEstimator) -> tuple[tuple[str, str], ...]:
        from sklearn.decomposition import NMF

        estimator = cast(NMF, estimator)
        details: list[tuple[str, str]] = []
        details += [
            ("Reconstruction error", f"{estimator.reconstruction_err_:.6g}"),
            ("Completed iterations", str(estimator.n_iter_)),
        ]
        return tuple(details)

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        params = self.parameters
        rows, width = values.shape
        if request.dimensions > min(rows, width):
            raise ValueError(
                "Output dimensions exceed sampled rows or varying feature count"
            )
        if params.scaling == "none" and np.any(values < 0):
            raise ValueError(
                "NMF needs nonnegative inputs; choose minmax scaling "
                "or disable standardization"
            )
