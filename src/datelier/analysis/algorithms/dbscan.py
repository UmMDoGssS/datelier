"""DBSCANAlgorithm: parameter ownership, fitting and input constraints."""

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import ClusterEstimator, ClusteringAlgorithm
from datelier.analysis.parameters import DBSCANParameters
from datelier.analysis.types import PreparedInput


class DBSCANAlgorithm(ClusteringAlgorithm[DBSCANParameters]):
    parameter_type = DBSCANParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import DBSCAN

        values = prepared.values
        params = self.parameters
        details: list[tuple[str, str]] = []
        estimator = DBSCAN(
            eps=params.epsilon,
            min_samples=params.min_samples,
            metric=params.metric,
            n_jobs=1,
        )
        return (estimator, values, tuple(details))
