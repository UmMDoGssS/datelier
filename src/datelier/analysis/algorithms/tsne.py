"""TSNEAlgorithm: parameter ownership, fitting and input constraints."""

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
from datelier.analysis.parameter_fields import choice, setting

if TYPE_CHECKING:
    from datelier.analysis.types import AnalysisRequest, PreparedInput


@dataclass(frozen=True)
class TSNEAlgorithm(DecompositionAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.TSNE
    perplexity: float = setting(30.0, "Perplexity", 1e-09)
    iterations: int = setting(1000, "Iterations", 250)
    learning_rate: float | str = field(
        default="auto",
        metadata={
            "label": "Learning rate",
            "kind": "real",
            "min": 1e-09,
            "max": 1000000.0,
            "automatic": "auto",
            "manual_default": 200.0,
        },
    )
    initialization: str = choice("pca", "Initialization", ("pca", "random"))
    recipe_kind: ClassVar[str] = "TSNEParameters"
    row_limit: ClassVar[int] = 10000
    default_row_limit: ClassVar[int] = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], Details]:
        from sklearn.manifold import TSNE

        request = prepared.request
        estimator = TSNE(
            n_components=request.dimensions,
            perplexity=self.perplexity,
            max_iter=self.iterations,
            learning_rate="auto"
            if self.learning_rate == "auto"
            else float(self.learning_rate),
            init="pca" if self.initialization == "pca" else "random",
            metric="euclidean",
            method="barnes_hut",
            random_state=request.seed,
            n_jobs=1,
        )
        return estimator, prepared.values, ()

    def diagnostics(self, estimator: EmbeddingEstimator) -> Details:
        from sklearn.manifold import TSNE

        model = cast(TSNE, estimator)
        return (
            ("KL divergence", f"{model.kl_divergence_:.6g}"),
            ("Completed iterations", str(model.n_iter_)),
            ("Distance", "Euclidean"),
            ("Method", "Barnes-Hut"),
        )

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        rows, width = values.shape
        if self.perplexity >= rows:
            raise ValueError(
                "t-SNE perplexity must be smaller than the sampled row count"
            )
        if self.initialization == "pca" and request.dimensions > min(rows, width):
            raise ValueError(
                "PCA initialization needs enough varying features for the dimensions"
            )
