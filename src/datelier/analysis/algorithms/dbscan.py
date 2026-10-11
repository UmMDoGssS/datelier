"""DBSCANAlgorithm: parameter ownership, fitting and input constraints."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import ClusterEstimator, ClusteringAlgorithm
from datelier.analysis.parameter_fields import choice, setting

if TYPE_CHECKING:
    from datelier.analysis.types import PreparedInput


@dataclass(frozen=True)
class DBSCANAlgorithm(ClusteringAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.DBSCAN
    epsilon: float = setting(0.5, "Neighborhood radius", 1e-09)
    min_samples: int = setting(5, "Minimum neighbors", 2, 10000)
    metric: str = choice("euclidean", "Distance", ("euclidean", "manhattan"))
    recipe_kind: ClassVar[str] = "DBSCANParameters"
    row_limit: ClassVar[int] = 5000
    default_row_limit: ClassVar[int] = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import DBSCAN

        values = prepared.values
        estimator = DBSCAN(
            eps=self.epsilon,
            min_samples=self.min_samples,
            metric=self.metric,
            n_jobs=1,
        )
        return (estimator, values, ())


# Legacy recipe/import name refers to this same algorithm, not a second record.
DBSCANParameters = DBSCANAlgorithm
