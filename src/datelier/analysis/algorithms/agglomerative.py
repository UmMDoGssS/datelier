"AgglomerativeAlgorithm: parameter ownership, fitting and input constraints."

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
class AgglomerativeParameters:
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.AGGLOMERATIVE
    clusters: int = setting(3, "Clusters", 1, 256)
    linkage: str = choice("ward", "Linkage", ("ward", "complete", "average", "single"))


class AgglomerativeAlgorithm(ClusteringAlgorithm[AgglomerativeParameters]):
    parameter_type = AgglomerativeParameters
    row_limit = 5000
    default_row_limit = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import AgglomerativeClustering

        values = prepared.values
        params = self.parameters
        details: list[tuple[str, str]] = []
        estimator = AgglomerativeClustering(
            n_clusters=params.clusters,
            linkage=cast(
                Literal["ward", "complete", "average", "single"], params.linkage
            ),
            metric="euclidean",
        )
        return (estimator, values, tuple(details))

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        params = self.parameters
        rows, width = values.shape
        if params.clusters > len(np.unique(values, axis=0)):
            raise ValueError("Cluster count exceeds distinct sampled inputs")
