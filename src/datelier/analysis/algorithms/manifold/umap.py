"""UMAPAlgorithm: parameter ownership, fitting and input constraints."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar
from warnings import catch_warnings, filterwarnings

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
class UMAPAlgorithm(DecompositionAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.UMAP
    neighbors: int = setting(15, "Neighbors", 2)
    min_distance: float = setting(0.1, "Minimum distance", 0, 1)
    metric: str = choice("euclidean", "Metric", ("euclidean", "cosine"))
    recipe_kind: ClassVar[str] = "UMAPParameters"
    row_limit: ClassVar[int] = 50000
    default_row_limit: ClassVar[int] = 5000

    libraries: ClassVar[tuple[str, ...]] = (
        "numpy",
        "polars",
        "scikit-learn",
        "umap-learn",
        "numba",
        "threadpoolctl",
    )

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], Details]:
        from numba import set_num_threads

        # Datelier uses ordinary UMAP; its separate TensorFlow estimator is not
        # required. Ignore only that optional-estimator import notice.
        with catch_warnings():
            filterwarnings(
                "ignore",
                message="Tensorflow not installed; ParametricUMAP will be unavailable$",
                category=ImportWarning,
                module="umap",
            )
            from umap import UMAP

        request = prepared.request
        set_num_threads(1)
        estimator = UMAP(
            n_components=request.dimensions,
            n_neighbors=self.neighbors,
            min_dist=self.min_distance,
            metric=self.metric,
            init="spectral",
            random_state=request.seed,
            transform_seed=request.seed,
            n_jobs=1,
            low_memory=True,
        )
        return (
            estimator,
            prepared.values,
            (
                ("Distance", self.metric),
                ("Initialization", "spectral"),
                ("Threads", "1"),
            ),
        )

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        rows, width = values.shape
        if self.neighbors >= rows or rows <= request.dimensions + 1:
            raise ValueError(
                "UMAP needs more sampled rows than neighbors and dimensions + 1"
            )
        if self.metric == "cosine" and np.any(np.linalg.norm(values, axis=1) == 0):
            raise ValueError(
                "Cosine distance is undefined for zero-valued preprocessed rows"
            )
