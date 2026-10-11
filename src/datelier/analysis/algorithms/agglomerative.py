"""AgglomerativeAlgorithm: parameter ownership, fitting and input constraints."""

from typing import Literal, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import ClusterEstimator, ClusteringAlgorithm
from datelier.analysis.parameters import AgglomerativeParameters
from datelier.analysis.types import AnalysisRequest, PreparedInput


class AgglomerativeAlgorithm(ClusteringAlgorithm[AgglomerativeParameters]):
    parameter_type = AgglomerativeParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import AgglomerativeClustering

        values = prepared.values
        params = self.parameters
        details: list[tuple[str, str]] = []
        estimator = AgglomerativeClustering(
            n_clusters=params.clusters,
            linkage=cast(
                Literal["ward", "complete", "average", "single"], params.linkage
            ),
            metric="euclidean",
        )
        return (estimator, values, tuple(details))

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        params = self.parameters
        rows, width = values.shape
        if params.clusters > len(np.unique(values, axis=0)):
            raise ValueError("Cluster count exceeds distinct sampled inputs")
