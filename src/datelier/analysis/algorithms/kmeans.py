"""KMeansAlgorithm: parameter ownership, fitting and input constraints."""

from typing import cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import ClusterEstimator, ClusteringAlgorithm
from datelier.analysis.types import (
    AnalysisRequest,
    KMeansFit,
    KMeansParameters,
    PreparedInput,
)


class KMeansAlgorithm(ClusteringAlgorithm[KMeansParameters]):
    parameter_type = KMeansParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import KMeans

        request = prepared.request
        values = prepared.values
        params = self.parameters
        _dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        estimator = KMeans(
            n_clusters=params.clusters,
            n_init=params.initializations,
            max_iter=params.iterations,
            random_state=seed,
        )
        return (estimator, values, tuple(details))

    def fitted_centers(
        self, estimator: ClusterEstimator, prepared: PreparedInput
    ) -> KMeansFit | None:
        from sklearn.cluster import KMeans

        estimator = cast(KMeans, estimator)
        return self.center_fit(
            prepared, estimator.cluster_centers_, float(estimator.inertia_)
        )

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        params = self.parameters
        rows, width = values.shape
        if params.clusters > len(np.unique(values, axis=0)):
            raise ValueError("Cluster count exceeds distinct sampled inputs")
