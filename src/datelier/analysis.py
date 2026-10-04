"""Explicit, isolated estimator boundary with complete settings provenance."""

from importlib.metadata import version
from time import perf_counter
from typing import cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis_types import (
    AnalysisResult,
    ClusteringResult,
    EmbeddingResult,
    KMeansParameters,
    PCAParameters,
    PreparedInput,
    Provenance,
)


def run_analysis(prepared: PreparedInput) -> AnalysisResult:
    started = perf_counter()
    request = prepared.request
    params = request.parameters
    if isinstance(params, KMeansParameters):
        from sklearn.cluster import KMeans

        estimator = KMeans(
            n_clusters=params.clusters,
            n_init=params.initializations,
            max_iter=params.iterations,
            random_state=request.seed,
        )
        labels = cast(NDArray[np.int64], estimator.fit_predict(prepared.values)).astype(
            np.int64
        )
        centers = cast(NDArray[np.float64], estimator.cluster_centers_).astype(
            np.float64
        )
        inertia = float(estimator.inertia_)
        if not np.isfinite(centers).all() or not np.isfinite(inertia):
            raise ValueError("Clustering overflow; enable standardization")
        labels.flags.writeable = centers.flags.writeable = False
        return ClusteringResult(
            prepared.revision,
            prepared.row_ids,
            labels,
            make_provenance(prepared, started),
            prepared.model,
            centers,
            tuple(int(v) for v in np.bincount(labels, minlength=params.clusters)),
            inertia,
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
    coordinates = cast(NDArray[np.float64], pca.fit_transform(prepared.values)).astype(
        np.float64
    )
    if (
        coordinates.shape != (len(prepared.row_ids), request.dimensions)
        or not np.isfinite(coordinates).all()
    ):
        raise ValueError("Analysis produced invalid coordinates")
    coordinates.flags.writeable = False
    provenance = make_provenance(prepared, started)
    return EmbeddingResult(
        prepared.revision,
        prepared.row_ids,
        prepared.positions,
        coordinates,
        provenance,
        (
            (
                "Explained variance ratio",
                str(pca.explained_variance_ratio_.tolist()),
            ),
        ),
    )


def make_provenance(
    prepared: PreparedInput,
    started: float,
    libraries: tuple[str, ...] = ("numpy", "polars", "scikit-learn"),
) -> Provenance:
    return Provenance(
        prepared.request,
        prepared.summary,
        tuple((name, version(name)) for name in libraries),
        perf_counter() - started,
    )
