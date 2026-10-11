"NMFAlgorithm: parameter ownership, fitting and input constraints."

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, cast

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
class NMFParameters:
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.NMF
    scaling: str = choice("minmax", "NMF input scaling", ("minmax", "none"))
    iterations: int = setting(500, "Iterations", 1, 10000)
    tolerance: float = setting(1e-4, "Tolerance", 1e-12, 1.0)


class NMFAlgorithm(FittedDecompositionAlgorithm[NMFParameters]):
    parameter_type = NMFParameters
    row_limit = 50000
    default_row_limit = 10000

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
