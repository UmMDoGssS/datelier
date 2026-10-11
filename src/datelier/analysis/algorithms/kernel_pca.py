"""KernelPCAAlgorithm: parameter ownership, fitting and input constraints."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Literal, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import (
    EmbeddingEstimator,
    FittedDecompositionAlgorithm,
)
from datelier.analysis.parameter_fields import choice

if TYPE_CHECKING:
    from datelier.analysis.types import AnalysisRequest, PreparedInput


@dataclass(frozen=True)
class KernelPCAAlgorithm(FittedDecompositionAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.KERNEL_PCA
    kernel: str = choice("rbf", "Kernel", ("rbf", "poly", "cosine", "linear"))
    gamma: float = field(
        default=1.0,
        metadata={
            "label": "Kernel gamma",
            "min": 1e-09,
            "max": 1000000.0,
            "unless": ("kernel", ("cosine", "linear")),
        },
    )
    degree: int = field(
        default=3,
        metadata={
            "label": "Polynomial degree",
            "min": 1,
            "max": 10,
            "when": ("kernel", "poly"),
        },
    )
    recipe_kind: ClassVar[str] = "KernelPCAParameters"
    row_limit: ClassVar[int] = 3000
    default_row_limit: ClassVar[int] = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.decomposition import KernelPCA

        request = prepared.request
        values = prepared.values
        dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        estimator = KernelPCA(
            n_components=dims,
            kernel=cast(Literal["rbf", "poly", "cosine", "linear"], self.kernel),
            gamma=self.gamma if self.kernel in ("rbf", "poly") else None,
            degree=self.degree if self.kernel == "poly" else 3,
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


# Legacy recipe/import name refers to this same algorithm, not a second record.
KernelPCAParameters = KernelPCAAlgorithm
