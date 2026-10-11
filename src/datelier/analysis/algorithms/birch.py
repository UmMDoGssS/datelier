"""BirchAlgorithm: parameter ownership, fitting and input constraints."""

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import ClusterEstimator, ClusteringAlgorithm
from datelier.analysis.parameters import BirchParameters
from datelier.analysis.types import AnalysisRequest, PreparedInput


class BirchAlgorithm(ClusteringAlgorithm[BirchParameters]):
    parameter_type = BirchParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import Birch

        values = prepared.values
        params = self.parameters
        details: list[tuple[str, str]] = []
        estimator = Birch(
            n_clusters=params.clusters,
            threshold=params.threshold,
            branching_factor=params.branching,
        )
        return (estimator, values, tuple(details))

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        params = self.parameters
        rows, width = values.shape
        if params.clusters > len(np.unique(values, axis=0)):
            raise ValueError("Cluster count exceeds distinct sampled inputs")
