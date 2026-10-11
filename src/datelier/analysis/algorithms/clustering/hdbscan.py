"""HDBSCANAlgorithm: parameter ownership, fitting and input constraints."""

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
class HDBSCANAlgorithm(ClusteringAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.HDBSCAN
    min_cluster_size: int = setting(5, "Minimum cluster size", 2, 10000)
    min_samples: int = setting(5, "Minimum neighbors", 2, 10000)
    selection: str = choice("eom", "Cluster selection", ("eom", "leaf"))
    allow_single_cluster: bool = field(
        default=False, metadata={"label": "Allow one cluster"}
    )
    recipe_kind: ClassVar[str] = "HDBSCANParameters"
    row_limit: ClassVar[int] = 10000
    default_row_limit: ClassVar[int] = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import (
            HDBSCAN,  # pyrefly: ignore [missing-module-attribute]
        )

        values = prepared.values
        estimator = HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=self.min_samples,
            cluster_selection_method=self.selection,
            allow_single_cluster=self.allow_single_cluster,
            n_jobs=1,
            copy=True,
        )
        return (estimator, values, ())

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        rows = len(values)
        if max(self.min_samples, self.min_cluster_size) > rows:
            raise ValueError(
                "Minimum neighbors and cluster size exceed the sampled rows"
            )
