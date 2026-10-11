"""PCAAlgorithm: parameter ownership, fitting and input constraints."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import (
    DecompositionAlgorithm,
    Details,
    EmbeddingEstimator,
)
from datelier.analysis.parameter_fields import choice

if TYPE_CHECKING:
    from datelier.analysis.types import AnalysisRequest, PreparedInput


@dataclass(frozen=True)
class PCAAlgorithm(DecompositionAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.PCA
    solver: str = choice("randomized", "Solver", ("randomized", "full"))
    whiten: bool = field(default=False, metadata={"label": "Whitening"})
    recipe_kind: ClassVar[str] = "PCAParameters"
    row_limit: ClassVar[int] = 100000
    default_row_limit: ClassVar[int] = 10000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], Details]:
        from sklearn.decomposition import PCA

        request = prepared.request
        estimator = PCA(
            n_components=request.dimensions,
            svd_solver="full" if self.solver == "full" else "randomized",
            whiten=self.whiten,
            random_state=request.seed,
        )
        return estimator, prepared.values, ()

    def diagnostics(self, estimator: EmbeddingEstimator) -> Details:
        from sklearn.decomposition import PCA

        model = cast(PCA, estimator)
        return (
            ("Explained variance ratio", str(model.explained_variance_ratio_.tolist())),
        )

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        rows, width = values.shape
        if request.dimensions > min(rows, width):
            raise ValueError(
                "PCA dimensions exceed the sampled rows or varying feature count"
            )
