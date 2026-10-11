"""PCAAlgorithm: parameter ownership, fitting and input constraints."""

from dataclasses import dataclass, field
from time import perf_counter
from typing import TYPE_CHECKING, ClassVar, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import DecompositionAlgorithm
from datelier.analysis.parameter_fields import choice

if TYPE_CHECKING:
    from datelier.analysis.types import AnalysisRequest, EmbeddingResult, PreparedInput


@dataclass(frozen=True)
class PCAAlgorithm(DecompositionAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.PCA
    solver: str = choice("randomized", "Solver", ("randomized", "full"))
    whiten: bool = field(default=False, metadata={"label": "Whitening"})
    recipe_kind: ClassVar[str] = "PCAParameters"
    row_limit: ClassVar[int] = 100000
    default_row_limit: ClassVar[int] = 10000

    def fit(self, prepared: PreparedInput) -> EmbeddingResult:
        from threadpoolctl import threadpool_limits

        from datelier.analysis.embedding_result import embedding_result

        self.check_input(prepared)
        started = perf_counter()
        request = prepared.request
        from sklearn.decomposition import PCA

        pca = PCA(
            n_components=request.dimensions,
            svd_solver="full" if self.solver == "full" else "randomized",
            whiten=self.whiten,
            random_state=request.seed,
        )
        with threadpool_limits(limits=1):
            coordinates = cast(
                NDArray[np.float64], pca.fit_transform(prepared.values)
            ).astype(np.float64)
        return embedding_result(
            prepared,
            coordinates,
            started,
            (
                (
                    "Explained variance ratio",
                    str(pca.explained_variance_ratio_.tolist()),
                ),
            ),
        )

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        rows, width = values.shape
        if request.dimensions > min(rows, width):
            raise ValueError(
                "PCA dimensions exceed the sampled rows or varying feature count"
            )


# Legacy recipe/import name refers to this same algorithm, not a second record.
PCAParameters = PCAAlgorithm
