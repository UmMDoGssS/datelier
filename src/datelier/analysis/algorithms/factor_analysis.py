"""FactorAnalysisAlgorithm: parameter ownership, fitting and input constraints."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Literal, cast

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
class FactorAnalysisAlgorithm(FittedDecompositionAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.FACTOR_ANALYSIS
    rotation: str = choice("none", "Rotation", ("none", "varimax", "quartimax"))
    iterations: int = setting(1000, "Iterations", 1, 10000)
    tolerance: float = setting(0.01, "Tolerance", 1e-12, 1.0)
    recipe_kind: ClassVar[str] = "FactorAnalysisParameters"
    row_limit: ClassVar[int] = 50000
    default_row_limit: ClassVar[int] = 10000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.decomposition import FactorAnalysis

        request = prepared.request
        values = prepared.values
        dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        rotation = (
            None
            if self.rotation == "none"
            else cast(Literal["varimax", "quartimax"], self.rotation)
        )
        estimator = FactorAnalysis(
            n_components=dims,
            rotation=rotation,
            max_iter=self.iterations,
            tol=self.tolerance,
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


# Legacy recipe/import name refers to this same algorithm, not a second record.
FactorAnalysisParameters = FactorAnalysisAlgorithm
