"""SpectralEmbeddingAlgorithm: parameter ownership, fitting and input constraints."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Literal, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import (
    DecompositionAlgorithm,
    EmbeddingEstimator,
)
from datelier.analysis.parameter_fields import choice

if TYPE_CHECKING:
    from datelier.analysis.types import AnalysisRequest, PreparedInput


@dataclass(frozen=True)
class SpectralEmbeddingAlgorithm(DecompositionAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.SPECTRAL_EMBEDDING
    affinity: str = choice(
        "nearest_neighbors", "Affinity", ("nearest_neighbors", "rbf")
    )
    neighbors: int = field(
        default=15,
        metadata={
            "label": "Neighbors",
            "min": 2,
            "max": 100,
            "when": ("affinity", "nearest_neighbors"),
        },
    )
    gamma: float = field(
        default=1.0,
        metadata={
            "label": "Kernel gamma",
            "min": 1e-09,
            "max": 1000000.0,
            "when": ("affinity", "rbf"),
        },
    )
    recipe_kind: ClassVar[str] = "SpectralEmbeddingParameters"
    row_limit: ClassVar[int] = 5000
    default_row_limit: ClassVar[int] = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.manifold import SpectralEmbedding

        request = prepared.request
        values = prepared.values
        dims, seed = (request.dimensions, request.seed)
        estimator = SpectralEmbedding(
            n_components=dims,
            affinity=cast(Literal["nearest_neighbors", "rbf"], self.affinity),
            n_neighbors=self.neighbors
            if self.affinity == "nearest_neighbors"
            else None,
            gamma=self.gamma if self.affinity == "rbf" else None,
            eigen_solver="arpack",
            random_state=seed,
            n_jobs=1,
        )
        return (estimator, values, ())

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        rows, width = values.shape
        if rows <= request.dimensions + 1:
            raise ValueError(
                "Manifold views need more sampled rows than dimensions + 1"
            )
        uses_neighbors = self.affinity == "nearest_neighbors"
        if uses_neighbors and self.neighbors >= rows:
            raise ValueError("Neighbors must be smaller than the sampled row count")
