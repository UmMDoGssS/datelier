"""MDSAlgorithm: parameter ownership, fitting and input constraints."""

from collections.abc import Callable
from typing import cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import (
    EmbeddingEstimator,
    FittedDecompositionAlgorithm,
)
from datelier.analysis.embedding_parameters import MDSParameters
from datelier.analysis.types import AnalysisRequest, PreparedInput


class MDSAlgorithm(FittedDecompositionAlgorithm[MDSParameters]):
    parameter_type = MDSParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.manifold import MDS

        request = prepared.request
        values = prepared.values
        params = self.parameters
        dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        mds_constructor = cast(Callable[..., MDS], MDS)
        estimator = mds_constructor(
            n_components=dims,
            metric_mds=params.metric,
            init=params.initialization,
            n_init=params.initializations if params.initialization == "random" else 1,
            max_iter=params.iterations,
            eps=params.tolerance,
            random_state=seed,
            n_jobs=1,
            normalized_stress="auto",
        )
        return (estimator, values, tuple(details))

    def diagnostics(self, estimator: EmbeddingEstimator) -> tuple[tuple[str, str], ...]:
        from sklearn.manifold import MDS

        estimator = cast(MDS, estimator)
        details: list[tuple[str, str]] = []
        details += [
            ("Stress", f"{estimator.stress_:.6g}"),
            ("Completed iterations", str(estimator.n_iter_)),
        ]
        return tuple(details)

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        rows, width = values.shape
        if rows <= request.dimensions:
            raise ValueError("MDS needs more sampled rows than dimensions")
