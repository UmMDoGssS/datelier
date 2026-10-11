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
class DBSCANParameters:
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.DBSCAN
    epsilon: float = setting(0.5, "Neighborhood radius", 1e-9)
    min_samples: int = setting(5, "Minimum neighbors", 2, 10000)
    metric: str = choice("euclidean", "Distance", ("euclidean", "manhattan"))


class DBSCANAlgorithm(ClusteringAlgorithm[DBSCANParameters]):
    parameter_type = DBSCANParameters
    row_limit = 5000
    default_row_limit = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import DBSCAN

        values = prepared.values
        params = self.parameters
        estimator = DBSCAN(
            eps=params.epsilon,
            min_samples=params.min_samples,
            metric=params.metric,
            n_jobs=1,
        )
        return estimator, values, ()
