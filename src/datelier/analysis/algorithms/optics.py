"""OPTICSAlgorithm: parameter ownership, fitting and input constraints."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import ClusterEstimator, ClusteringAlgorithm
from datelier.analysis.parameter_fields import choice, setting

if TYPE_CHECKING:
    from datelier.analysis.types import AnalysisRequest, PreparedInput


@dataclass(frozen=True)
class OPTICSParameters:
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.OPTICS
    min_samples: int = setting(5, "Minimum neighbors", 2, 10000)
    min_cluster_size: int = setting(5, "Minimum cluster size", 2, 10000)
    xi: float = setting(0.05, "Steepness threshold", 1e-6, 0.999999)
    metric: str = choice("euclidean", "Distance", ("euclidean", "manhattan"))


class OPTICSAlgorithm(ClusteringAlgorithm[OPTICSParameters]):
    parameter_type = OPTICSParameters
    row_limit = 5000
    default_row_limit = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import OPTICS

        values = prepared.values
        params = self.parameters
        estimator = OPTICS(
            min_samples=params.min_samples,
            min_cluster_size=params.min_cluster_size,
            xi=params.xi,
            metric=params.metric,
            n_jobs=1,
        )
        return estimator, values, ()

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        params = self.parameters
        rows = len(values)
        if max(params.min_samples, params.min_cluster_size) > rows:
            raise ValueError(
                "Minimum neighbors and cluster size exceed the sampled rows"
            )
