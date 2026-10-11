"""BirchAlgorithm: parameter ownership, fitting and input constraints."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import ClusterEstimator, ClusteringAlgorithm
from datelier.analysis.parameter_fields import setting

if TYPE_CHECKING:
    from datelier.analysis.types import AnalysisRequest, PreparedInput


@dataclass(frozen=True)
class BirchParameters:
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.BIRCH
    clusters: int = setting(3, "Clusters", 1, 256)
    threshold: float = setting(0.5, "Subcluster radius", 1e-9)
    branching: int = setting(50, "Branching factor", 2, 1000)


class BirchAlgorithm(ClusteringAlgorithm[BirchParameters]):
    parameter_type = BirchParameters
    row_limit = 100000
    default_row_limit = 10000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import Birch

        values = prepared.values
        params = self.parameters
        estimator = Birch(
            n_clusters=params.clusters,
            threshold=params.threshold,
            branching_factor=params.branching,
        )
        return estimator, values, ()

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        params = self.parameters
        if params.clusters > len(np.unique(values, axis=0)):
            raise ValueError("Cluster count exceeds distinct sampled inputs")
