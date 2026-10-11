"MiniBatchAlgorithm: parameter ownership, fitting and input constraints."

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import ClusterEstimator, ClusteringAlgorithm
from datelier.analysis.parameter_fields import setting

if TYPE_CHECKING:
    from datelier.analysis.types import AnalysisRequest, KMeansFit, PreparedInput


@dataclass(frozen=True)
class MiniBatchParameters:
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.MINIBATCH_KMEANS
    clusters: int = setting(3, "Clusters", 1, 256)
    batch_size: int = setting(1024, "Batch size", 1, 100000)
    initializations: int = setting(3, "Initializations", 1, 100)
    iterations: int = setting(100, "Iterations", 1, 10000)


class MiniBatchAlgorithm(ClusteringAlgorithm[MiniBatchParameters]):
    parameter_type = MiniBatchParameters
    row_limit = 100000
    default_row_limit = 10000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import MiniBatchKMeans

        request = prepared.request
        values = prepared.values
        params = self.parameters
        _dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        estimator = MiniBatchKMeans(
            n_clusters=params.clusters,
            batch_size=params.batch_size,
            n_init=params.initializations,
            max_iter=params.iterations,
            random_state=seed,
        )
        return (estimator, values, tuple(details))

    def fitted_centers(
        self, estimator: ClusterEstimator, prepared: PreparedInput
    ) -> KMeansFit | None:
        from sklearn.cluster import MiniBatchKMeans

        estimator = cast(MiniBatchKMeans, estimator)
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
