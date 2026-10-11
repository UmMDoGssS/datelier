"""LLEAlgorithm: parameter ownership, fitting and input constraints."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Literal, cast

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
class LLEAlgorithm(DecompositionAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.LLE
    method: str = choice(
        "standard", "LLE method", ("standard", "modified", "hessian", "ltsa")
    )
    neighbors: int = setting(15, "Neighbors", 2, 100)
    regularization: float = field(
        default=0.001,
        metadata={
            "label": "Local regularization",
            "min": 1e-12,
            "max": 1.0,
            "when": ("method", "standard"),
        },
    )
    recipe_kind: ClassVar[str] = "LLEParameters"
    row_limit: ClassVar[int] = 2000
    default_row_limit: ClassVar[int] = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.manifold import LocallyLinearEmbedding

        request = prepared.request
        values = prepared.values
        dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        estimator = LocallyLinearEmbedding(
            n_components=dims,
            n_neighbors=self.neighbors,
            method=cast(
                Literal["standard", "modified", "hessian", "ltsa"], self.method
            ),
            reg=self.regularization if self.method == "standard" else 0.001,
            eigen_solver="dense",
            random_state=seed,
            n_jobs=1,
        )
        return (estimator, values, tuple(details))

    def diagnostics(self, estimator: EmbeddingEstimator) -> tuple[tuple[str, str], ...]:
        from sklearn.manifold import LocallyLinearEmbedding

        estimator = cast(LocallyLinearEmbedding, estimator)
        details: list[tuple[str, str]] = []
        details.append(
            ("Reconstruction error", f"{estimator.reconstruction_error_:.6g}")
        )
        return tuple(details)

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
        if request.dimensions > width:
            raise ValueError("LLE dimensions exceed the varying feature count")
        minimum = (
            request.dimensions * (request.dimensions + 3) / 2
            if self.method == "hessian"
            else request.dimensions
        )
        if self.neighbors <= minimum:
            raise ValueError(f"{self.method} LLE needs more than {minimum:g} neighbors")
