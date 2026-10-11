"""OPTICSAlgorithm: parameter ownership, fitting and input constraints."""

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import ClusterEstimator, ClusteringAlgorithm
from datelier.analysis.parameters import OPTICSParameters
from datelier.analysis.types import AnalysisRequest, PreparedInput


class OPTICSAlgorithm(ClusteringAlgorithm[OPTICSParameters]):
    parameter_type = OPTICSParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import OPTICS

        values = prepared.values
        params = self.parameters
        details: list[tuple[str, str]] = []
        estimator = OPTICS(
            min_samples=params.min_samples,
            min_cluster_size=params.min_cluster_size,
            xi=params.xi,
            metric=params.metric,
            n_jobs=1,
        )
        return (estimator, values, tuple(details))

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        params = self.parameters
        rows, width = values.shape
        if max(params.min_samples, params.min_cluster_size) > rows:
            raise ValueError(
                "Minimum neighbors and cluster size exceed the sampled rows"
            )
