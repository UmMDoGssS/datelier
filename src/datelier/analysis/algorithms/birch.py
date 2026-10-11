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
class BirchAlgorithm(ClusteringAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.BIRCH
    clusters: int = setting(3, "Clusters", 1, 256)
    threshold: float = setting(0.5, "Subcluster radius", 1e-09)
    branching: int = setting(50, "Branching factor", 2, 1000)
    recipe_kind: ClassVar[str] = "BirchParameters"
    row_limit: ClassVar[int] = 100000
    default_row_limit: ClassVar[int] = 10000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import Birch

        values = prepared.values
        estimator = Birch(
            n_clusters=self.clusters,
            threshold=self.threshold,
            branching_factor=self.branching,
        )
        return (estimator, values, ())

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        if self.clusters > len(np.unique(values, axis=0)):
            raise ValueError("Cluster count exceeds distinct sampled inputs")


# Legacy recipe/import name refers to this same algorithm, not a second record.
BirchParameters = BirchAlgorithm
