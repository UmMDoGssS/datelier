"""Explicit clustering estimators in the owned analysis worker."""

from time import perf_counter
from typing import Literal, cast
from warnings import catch_warnings

import numpy as np
from numpy.typing import NDArray

from datelier.analysis_parameters import (
    AffinityPropagationParameters,
    AgglomerativeParameters,
    BayesianMixtureParameters,
    BirchParameters,
    DBSCANParameters,
    GaussianMixtureParameters,
    HDBSCANParameters,
    MeanShiftParameters,
    MiniBatchParameters,
    OPTICSParameters,
    SpectralClusteringParameters,
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
        AffinityPropagation,
        AgglomerativeClustering,
        Birch,
        KMeans,
        MeanShift,
        MiniBatchKMeans,
        SpectralClustering,
        estimate_bandwidth,
    )
    from sklearn.mixture import BayesianGaussianMixture, GaussianMixture
    from threadpoolctl import threadpool_limits

    started = perf_counter()
    params, seed = prepared.request.parameters, prepared.request.seed
    details: list[tuple[str, str]] = []
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
    elif isinstance(params, MiniBatchParameters):
        estimator = MiniBatchKMeans(
            n_clusters=params.clusters,
            batch_size=params.batch_size,
            n_init=params.initializations,
            max_iter=params.iterations,
            random_state=seed,
        )
    elif isinstance(params, GaussianMixtureParameters):
        estimator = GaussianMixture(
            n_components=params.clusters,
            covariance_type=cast(
                Literal["full", "tied", "diag", "spherical"], params.covariance
            ),
            reg_covar=params.regularization,
            n_init=params.initializations,
            max_iter=params.iterations,
            random_state=seed,
        )
    elif isinstance(params, BayesianMixtureParameters):
        estimator = BayesianGaussianMixture(
            n_components=params.clusters,
            covariance_type=cast(
                Literal["full", "tied", "diag", "spherical"], params.covariance
            ),
            weight_concentration_prior=params.concentration,
            reg_covar=params.regularization,
            max_iter=params.iterations,
            random_state=seed,
        )
    elif isinstance(params, AgglomerativeParameters):
        estimator = AgglomerativeClustering(
            n_clusters=params.clusters,
            linkage=cast(
                Literal["ward", "complete", "average", "single"], params.linkage
            ),
            metric="euclidean",
        )
    elif isinstance(params, BirchParameters):
        estimator = Birch(
            n_clusters=params.clusters,
            threshold=params.threshold,
            branching_factor=params.branching,
        )
    elif isinstance(params, MeanShiftParameters):
        with threadpool_limits(limits=1):
            bandwidth = (
                float(
                    estimate_bandwidth(
                        prepared.values,
                        quantile=params.quantile,
                        n_samples=min(500, len(prepared.row_ids)),
                        random_state=seed,
                        n_jobs=1,
                    )
                )
                if params.automatic_bandwidth
                else params.bandwidth
            )
        if not np.isfinite(bandwidth) or bandwidth <= 0:
            raise ValueError(
                "Estimated bandwidth is zero; choose a positive manual bandwidth"
            )
        details.append(("Fitted bandwidth", f"{bandwidth:.6g}"))
        estimator = MeanShift(
            bandwidth=bandwidth,
            cluster_all=params.cluster_all,
            max_iter=params.iterations,
            n_jobs=1,
        )
    elif isinstance(params, SpectralClusteringParameters):
        estimator = SpectralClustering(
            n_clusters=params.clusters,
            affinity=params.affinity,
            n_neighbors=params.neighbors
            if params.affinity == "nearest_neighbors"
            else 10,
            gamma=params.gamma if params.affinity == "rbf" else 1.0,
            n_init=params.initializations,
            random_state=seed,
            n_jobs=1,
        )
    elif isinstance(params, AffinityPropagationParameters):
        estimator = AffinityPropagation(
            damping=params.damping,
            max_iter=params.iterations,
            convergence_iter=params.convergence_iterations,
            preference=None if params.automatic_preference else params.preference,
            random_state=seed,
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
    if isinstance(estimator, (KMeans, MiniBatchKMeans)):
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
    if isinstance(estimator, (GaussianMixture, BayesianGaussianMixture)):
        details += [
            ("Converged", str(estimator.converged_)),
            ("Completed iterations", str(estimator.n_iter_)),
            ("Lower bound", f"{estimator.lower_bound_:.6g}"),
        ]
    if isinstance(estimator, AffinityPropagation) and np.all(labels < 0):
        raise ValueError(
            "Affinity propagation found no assignments; "
            "adjust damping, preference or iterations"
        )
    if fit is None:
        # Compact component labels when a mixture leaves some components unused.
        positive = labels >= 0
        labels[positive] = np.searchsorted(
            np.unique(labels[positive]), labels[positive]
        )
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
        (*details, *(("Fit warning", str(w.message)) for w in captured)),
    )
