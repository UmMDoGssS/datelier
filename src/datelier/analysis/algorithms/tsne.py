"TSNEAlgorithm: parameter ownership, fitting and input constraints."

from dataclasses import dataclass, field
from time import perf_counter
from typing import TYPE_CHECKING, ClassVar, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import DecompositionAlgorithm
from datelier.analysis.parameter_fields import choice, setting

if TYPE_CHECKING:
    from datelier.analysis.types import AnalysisRequest, EmbeddingResult, PreparedInput


@dataclass(frozen=True)
class TSNEParameters:
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.TSNE
    perplexity: float = setting(30.0, "Perplexity", 1e-9)
    iterations: int = setting(1000, "Iterations", 250)
    learning_rate: float | str = field(
        default="auto",
        metadata={
            "label": "Learning rate",
            "kind": "real",
            "min": 1e-9,
            "max": 1e6,
            "automatic": "auto",
            "manual_default": 200.0,
        },
    )
    initialization: str = choice("pca", "Initialization", ("pca", "random"))


class TSNEAlgorithm(DecompositionAlgorithm[TSNEParameters]):
    parameter_type = TSNEParameters
    row_limit = 10000
    default_row_limit = 2000

    def run(self, prepared: PreparedInput) -> EmbeddingResult:
        from threadpoolctl import threadpool_limits

        from datelier.analysis.embedding_result import embedding_result

        started = perf_counter()
        request = prepared.request
        params = self.parameters
        from sklearn.manifold import TSNE

        tsne = TSNE(
            n_components=request.dimensions,
            perplexity=params.perplexity,
            max_iter=params.iterations,
            learning_rate="auto"
            if params.learning_rate == "auto"
            else float(params.learning_rate),
            init="pca" if params.initialization == "pca" else "random",
            metric="euclidean",
            method="barnes_hut",
            random_state=request.seed,
            n_jobs=1,
        )
        with threadpool_limits(limits=1):
            coordinates = cast(
                NDArray[np.float64], tsne.fit_transform(prepared.values)
            ).astype(np.float64)
        return embedding_result(
            prepared,
            coordinates,
            started,
            (
                ("KL divergence", f"{tsne.kl_divergence_:.6g}"),
                ("Completed iterations", str(tsne.n_iter_)),
                ("Distance", "Euclidean"),
                ("Method", "Barnes-Hut"),
            ),
        )

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        params = self.parameters
        rows, width = values.shape
        if params.perplexity >= rows:
            raise ValueError(
                "t-SNE perplexity must be smaller than the sampled row count"
            )
        if params.initialization == "pca" and request.dimensions > min(rows, width):
            raise ValueError(
                "PCA initialization needs enough varying features for the dimensions"
            )
