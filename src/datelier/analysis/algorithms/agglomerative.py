"""AgglomerativeAlgorithm: parameter ownership, fitting and input constraints."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Literal, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import ClusterEstimator, ClusteringAlgorithm
from datelier.analysis.parameter_fields import choice, setting

if TYPE_CHECKING:
    from datelier.analysis.types import AnalysisRequest, PreparedInput


@dataclass(frozen=True)
class AgglomerativeAlgorithm(ClusteringAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.AGGLOMERATIVE
    clusters: int = setting(3, "Clusters", 1, 256)
    linkage: str = choice("ward", "Linkage", ("ward", "complete", "average", "single"))
    recipe_kind: ClassVar[str] = "AgglomerativeParameters"
    row_limit: ClassVar[int] = 5000
    default_row_limit: ClassVar[int] = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import AgglomerativeClustering

        values = prepared.values
        estimator = AgglomerativeClustering(
            n_clusters=self.clusters,
            linkage=cast(
                Literal["ward", "complete", "average", "single"], self.linkage
            ),
            metric="euclidean",
        )
        return (estimator, values, ())

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        if self.clusters > len(np.unique(values, axis=0)):
            raise ValueError("Cluster count exceeds distinct sampled inputs")
