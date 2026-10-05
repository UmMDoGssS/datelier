"""Bounded manifold estimators, separate from GUI and data preparation."""

from collections.abc import Callable
from time import perf_counter
from typing import Literal, cast
from warnings import catch_warnings

import numpy as np
from numpy.typing import NDArray

from datelier.analysis_embedding_result import embedding_result
from datelier.analysis_types import EmbeddingResult, PreparedInput
from datelier.embedding_parameters import (
    IsomapParameters,
    LLEParameters,
    MDSParameters,
    SpectralEmbeddingParameters,
)


def run_manifold(prepared: PreparedInput) -> EmbeddingResult:
    from sklearn.manifold import MDS, Isomap, LocallyLinearEmbedding, SpectralEmbedding
    from threadpoolctl import threadpool_limits

    started = perf_counter()
    request = prepared.request
    params, dims, seed = request.parameters, request.dimensions, request.seed
    if isinstance(params, IsomapParameters):
        estimator = Isomap(
            n_neighbors=params.neighbors,
            n_components=dims,
            metric=params.metric,
            eigen_solver="dense",
            path_method="D",
            n_jobs=1,
        )
    elif isinstance(params, MDSParameters):
        # Installed 1.9 API renamed metric_mds and added init; stubs lag behind.
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
    elif isinstance(params, SpectralEmbeddingParameters):
        estimator = SpectralEmbedding(
            n_components=dims,
            affinity=cast(Literal["nearest_neighbors", "rbf"], params.affinity),
            n_neighbors=params.neighbors
            if params.affinity == "nearest_neighbors"
            else None,
            gamma=params.gamma if params.affinity == "rbf" else None,
            eigen_solver="arpack",
            random_state=seed,
            n_jobs=1,
        )
    elif isinstance(params, LLEParameters):
        # Dense solving avoids singular-neighborhood failures; rows capped at 2k.
        estimator = LocallyLinearEmbedding(
            n_components=dims,
            n_neighbors=params.neighbors,
            method=cast(
                Literal["standard", "modified", "hessian", "ltsa"], params.method
            ),
            reg=params.regularization if params.method == "standard" else 0.001,
            eigen_solver="dense",
            random_state=seed,
            n_jobs=1,
        )
    else:
        raise NotImplementedError(f"No manifold runner for {request.algorithm}")
    with catch_warnings(record=True) as captured, threadpool_limits(limits=1):
        coordinates = cast(
            NDArray[np.float64], estimator.fit_transform(prepared.values)
        ).astype(np.float64)
    details: list[tuple[str, str]] = []
    if isinstance(estimator, MDS):
        details += [
            ("Stress", f"{estimator.stress_:.6g}"),
            ("Completed iterations", str(estimator.n_iter_)),
        ]
    if isinstance(estimator, LocallyLinearEmbedding):
        details.append(
            ("Reconstruction error", f"{estimator.reconstruction_error_:.6g}")
        )
    details += [("Fit warning", str(w.message)) for w in captured]
    return embedding_result(prepared, coordinates, started, tuple(details))
