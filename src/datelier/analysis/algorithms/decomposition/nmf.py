"""NMFAlgorithm: parameter ownership, fitting and input constraints."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import (
    DecompositionAlgorithm,
    EmbeddingEstimator,
)
from datelier.analysis.parameter_fields import choice, setting

if TYPE_CHECKING:
    from datelier.analysis.types import AnalysisRequest, PreparedInput


@dataclass(frozen=True)
class NMFAlgorithm(DecompositionAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.NMF
    scaling: str = choice("minmax", "NMF input scaling", ("minmax", "none"))
    iterations: int = setting(500, "Iterations", 1, 10000)
    tolerance: float = setting(0.0001, "Tolerance", 1e-12, 1.0)
    recipe_kind: ClassVar[str] = "NMFParameters"
    row_limit: ClassVar[int] = 50000
    default_row_limit: ClassVar[int] = 10000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.decomposition import NMF

        request = prepared.request
        values = prepared.values
        dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        if self.scaling == "minmax":
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
            max_iter=self.iterations,
            tol=self.tolerance,
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
        rows, width = values.shape
        if request.dimensions > min(rows, width):
            raise ValueError(
                "Output dimensions exceed sampled rows or varying feature count"
            )
        if self.scaling == "none" and np.any(values < 0):
            raise ValueError(
                "NMF needs nonnegative inputs; choose minmax scaling "
                "or disable standardization"
            )
