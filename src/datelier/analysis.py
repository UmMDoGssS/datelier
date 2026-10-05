"""Explicit, isolated estimator boundary with complete settings provenance."""

from time import perf_counter
from typing import cast
from warnings import catch_warnings

import numpy as np
from numpy.typing import NDArray

from datelier.analysis_provenance import make_provenance
from datelier.analysis_types import (
    AnalysisResult,
    EmbeddingResult,
    PCAParameters,
    PreparedInput,
    TSNEParameters,
    UMAPParameters,
)


def run_analysis(prepared: PreparedInput) -> AnalysisResult:
    from threadpoolctl import threadpool_limits

    started = perf_counter()
    request = prepared.request
    params = request.parameters
    if request.algorithm.is_clustering:
        from datelier.analysis_clustering import run_clustering

        return run_clustering(prepared)
    if isinstance(params, TSNEParameters):
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
    if isinstance(params, UMAPParameters):
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
    if not isinstance(params, PCAParameters):
        raise NotImplementedError(f"{request.algorithm} runner is not implemented yet")
    # Estimator imports stay inside the owned worker (never GUI import/startup).
    from sklearn.decomposition import PCA

    pca = PCA(
        n_components=request.dimensions,
        svd_solver="full" if params.solver == "full" else "randomized",
        whiten=params.whiten,
        random_state=request.seed,
    )
    # Narrow cast at scikit-learn's dynamic estimator-array boundary.
    with threadpool_limits(limits=1):
        coordinates = cast(
            NDArray[np.float64], pca.fit_transform(prepared.values)
        ).astype(np.float64)
    return embedding_result(
        prepared,
        coordinates,
        started,
        (("Explained variance ratio", str(pca.explained_variance_ratio_.tolist())),),
    )


def embedding_result(
    prepared: PreparedInput,
    coordinates: NDArray[np.float64],
    started: float,
    details: tuple[tuple[str, str], ...],
    libraries: tuple[str, ...] = ("numpy", "polars", "scikit-learn", "threadpoolctl"),
) -> EmbeddingResult:
    if (
        coordinates.shape != (len(prepared.row_ids), prepared.request.dimensions)
        or not np.isfinite(coordinates).all()
    ):
        raise ValueError("Analysis produced invalid coordinates")
    coordinates.flags.writeable = False
    return EmbeddingResult(
        prepared.revision,
        prepared.row_ids,
        prepared.positions,
        coordinates,
        make_provenance(prepared, started, libraries),
        details,
    )
