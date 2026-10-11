"""KMeansAlgorithm: parameter ownership, fitting and input constraints."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import (
    ClusterEstimator,
    NearestCenterClusteringAlgorithm,
)
from datelier.analysis.parameter_fields import setting

if TYPE_CHECKING:
    from datelier.analysis.types import AnalysisRequest, KMeansFit, PreparedInput


@dataclass(frozen=True)
class KMeansAlgorithm(NearestCenterClusteringAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.KMEANS
    clusters: int = setting(3, "Clusters", 1, 256)
    initializations: int = setting(10, "Initializations", 1)
    iterations: int = setting(300, "Iterations", 1)
    recipe_kind: ClassVar[str] = "KMeansParameters"
    row_limit: ClassVar[int] = 100000
    default_row_limit: ClassVar[int] = 10000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import KMeans

        request = prepared.request
        values = prepared.values
        seed = request.seed
        estimator = KMeans(
            n_clusters=self.clusters,
            n_init=self.initializations,
            max_iter=self.iterations,
            random_state=seed,
        )
        return (estimator, values, ())

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
        if self.clusters > len(np.unique(values, axis=0)):
            raise ValueError("Cluster count exceeds distinct sampled inputs")
