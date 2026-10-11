"""SpectralClusteringAlgorithm: parameter ownership, fitting and input constraints."""

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import ClusterEstimator, ClusteringAlgorithm
from datelier.analysis.parameters import SpectralClusteringParameters
from datelier.analysis.types import AnalysisRequest, PreparedInput


class SpectralClusteringAlgorithm(ClusteringAlgorithm[SpectralClusteringParameters]):
    parameter_type = SpectralClusteringParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import SpectralClustering

        request = prepared.request
        values = prepared.values
        params = self.parameters
        _dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
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
        return (estimator, values, tuple(details))

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        params = self.parameters
        rows, width = values.shape
        if params.clusters > len(np.unique(values, axis=0)):
            raise ValueError("Cluster count exceeds distinct sampled inputs")
        if params.affinity == "nearest_neighbors" and params.neighbors >= rows:
            raise ValueError(
                "Spectral clustering needs more sampled rows than neighbors"
            )
