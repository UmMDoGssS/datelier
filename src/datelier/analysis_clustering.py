"""Explicit clustering estimators in the owned analysis worker."""

from time import perf_counter
from typing import cast
from warnings import catch_warnings

import numpy as np
from numpy.typing import NDArray

from datelier.analysis_parameters import (
    DBSCANParameters,
    HDBSCANParameters,
    OPTICSParameters,
)
from datelier.analysis_provenance import make_provenance
from datelier.analysis_types import (
    ClusteringResult,
    KMeansFit,
    KMeansParameters,
    PreparedInput,
)


def run_clustering(prepared: PreparedInput) -> ClusteringResult:
    # Installed public HDBSCAN exists; sklearn-stubs omits its re-export.
    from sklearn.cluster import (
        DBSCAN,
        HDBSCAN,  # pyrefly: ignore [missing-module-attribute]
        OPTICS,
        KMeans,
    )
    from threadpoolctl import threadpool_limits

    started = perf_counter()
    params, seed = prepared.request.parameters, prepared.request.seed
    if isinstance(params, KMeansParameters):
        estimator = KMeans(
            n_clusters=params.clusters,
            n_init=params.initializations,
            max_iter=params.iterations,
            random_state=seed,
        )
    elif isinstance(params, DBSCANParameters):
        estimator = DBSCAN(
            eps=params.epsilon,
            min_samples=params.min_samples,
            metric=params.metric,
            n_jobs=1,
        )
    elif isinstance(params, HDBSCANParameters):
        estimator = HDBSCAN(
            min_cluster_size=params.min_cluster_size,
            min_samples=params.min_samples,
            cluster_selection_method=params.selection,
            allow_single_cluster=params.allow_single_cluster,
            n_jobs=1,
            copy=True,
        )
    elif isinstance(params, OPTICSParameters):
        estimator = OPTICS(
            min_samples=params.min_samples,
            min_cluster_size=params.min_cluster_size,
            xi=params.xi,
            metric=params.metric,
            n_jobs=1,
        )
    else:
        raise NotImplementedError(
            f"No clustering runner for {prepared.request.algorithm}"
        )
    with catch_warnings(record=True) as captured, threadpool_limits(limits=1):
        labels = cast(NDArray[np.int64], estimator.fit_predict(prepared.values)).astype(
            np.int64
        )
    fit = None
    if isinstance(estimator, KMeans):
        centers = cast(NDArray[np.float64], estimator.cluster_centers_).astype(
            np.float64
        )
        inertia = float(estimator.inertia_)
        if not np.isfinite(centers).all() or not np.isfinite(inertia):
            raise ValueError("Clustering overflow; enable standardization")
        centers.flags.writeable = False
        fit = KMeansFit(prepared.model, centers, inertia)
    if labels.shape != (len(prepared.row_ids),) or np.any(labels < -1):
        raise ValueError("Analysis produced invalid cluster assignments")
    counts = tuple(int(v) for v in np.bincount(labels[labels >= 0]))
    labels.flags.writeable = False
    return ClusteringResult(
        prepared.revision,
        prepared.row_ids,
        labels,
        make_provenance(prepared, started),
        counts,
        fit,
        int(np.count_nonzero(labels == -1)),
        tuple(("Fit warning", str(w.message)) for w in captured),
    )
