"""UMAPAlgorithm: parameter ownership, fitting and input constraints."""

from time import perf_counter
from typing import cast
from warnings import catch_warnings

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import DecompositionAlgorithm
from datelier.analysis.embedding_result import embedding_result
from datelier.analysis.types import (
    AnalysisRequest,
    EmbeddingResult,
    PreparedInput,
    UMAPParameters,
)


class UMAPAlgorithm(DecompositionAlgorithm[UMAPParameters]):
    parameter_type = UMAPParameters

    def run(self, prepared: PreparedInput) -> EmbeddingResult:
        from threadpoolctl import threadpool_limits

        started = perf_counter()
        request = prepared.request
        params = self.parameters
        from numba import set_num_threads
        from umap import UMAP

        set_num_threads(1)
        reducer = UMAP(
            n_components=request.dimensions,
            n_neighbors=params.neighbors,
            min_dist=params.min_distance,
            metric=params.metric,
            init="spectral",
            random_state=request.seed,
            transform_seed=request.seed,
            n_jobs=1,
            low_memory=True,
        )
        with catch_warnings(record=True) as captured, threadpool_limits(limits=1):
            coordinates = cast(
                NDArray[np.float64], reducer.fit_transform(prepared.values)
            ).astype(np.float64)
        warnings = tuple(("Fit warning", str(item.message)) for item in captured)
        return embedding_result(
            prepared,
            coordinates,
            started,
            (
                ("Distance", params.metric),
                ("Initialization", "spectral"),
                ("Threads", "1"),
                *warnings,
            ),
            ("numpy", "polars", "scikit-learn", "umap-learn", "numba", "threadpoolctl"),
        )

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        params = self.parameters
        rows, width = values.shape
        if params.neighbors >= rows or rows <= request.dimensions + 1:
            raise ValueError(
                "UMAP needs more sampled rows than neighbors and dimensions + 1"
            )
        if params.metric == "cosine" and np.any(np.linalg.norm(values, axis=1) == 0):
            raise ValueError(
                "Cosine distance is undefined for zero-valued preprocessed rows"
            )
