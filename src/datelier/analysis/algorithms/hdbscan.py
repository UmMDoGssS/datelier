"HDBSCANAlgorithm: parameter ownership, fitting and input constraints."

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import ClusterEstimator, ClusteringAlgorithm
from datelier.analysis.parameter_fields import choice, setting

if TYPE_CHECKING:
    from datelier.analysis.types import AnalysisRequest, PreparedInput


@dataclass(frozen=True)
class HDBSCANParameters:
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.HDBSCAN
    min_cluster_size: int = setting(5, "Minimum cluster size", 2, 10000)
    min_samples: int = setting(5, "Minimum neighbors", 2, 10000)
    selection: str = choice("eom", "Cluster selection", ("eom", "leaf"))
    allow_single_cluster: bool = field(
        default=False, metadata={"label": "Allow one cluster"}
    )


class HDBSCANAlgorithm(ClusteringAlgorithm[HDBSCANParameters]):
    parameter_type = HDBSCANParameters
    row_limit = 10000
    default_row_limit = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import (
            HDBSCAN,  # pyrefly: ignore [missing-module-attribute]
        )

        values = prepared.values
        params = self.parameters
        details: list[tuple[str, str]] = []
        estimator = HDBSCAN(
            min_cluster_size=params.min_cluster_size,
            min_samples=params.min_samples,
            cluster_selection_method=params.selection,
            allow_single_cluster=params.allow_single_cluster,
            n_jobs=1,
            copy=True,
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
