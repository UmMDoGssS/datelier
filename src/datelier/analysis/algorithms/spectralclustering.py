"SpectralClusteringAlgorithm: parameter ownership, fitting and input constraints."

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
class SpectralClusteringParameters:
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.SPECTRAL_CLUSTERING
    clusters: int = setting(3, "Clusters", 1, 256)
    affinity: str = choice(
        "nearest_neighbors", "Affinity", ("nearest_neighbors", "rbf")
    )
    neighbors: int = field(
        default=10,
        metadata={
            "label": "Neighbors",
            "min": 2,
            "max": 10000,
            "when": ("affinity", "nearest_neighbors"),
        },
    )
    gamma: float = field(
        default=1.0,
        metadata={
            "label": "Kernel gamma",
            "min": 1e-9,
            "max": 1e6,
            "when": ("affinity", "rbf"),
        },
    )
    initializations: int = setting(10, "Initializations", 1, 100)


class SpectralClusteringAlgorithm(ClusteringAlgorithm[SpectralClusteringParameters]):
    parameter_type = SpectralClusteringParameters
    row_limit = 3000
    default_row_limit = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import SpectralClustering

        request = prepared.request
        values = prepared.values
        params = self.parameters
        _dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        estimator = SpectralClustering(
            n_clusters=params.clusters,
            affinity=params.affinity,
            n_neighbors=params.neighbors
            if params.affinity == "nearest_neighbors"
            else 10,
            gamma=params.gamma if params.affinity == "rbf" else 1.0,
            n_init=params.initializations,
            random_state=seed,
            n_jobs=1,
        )
        return (estimator, values, tuple(details))

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        params = self.parameters
        rows, width = values.shape
        if params.clusters > len(np.unique(values, axis=0)):
            raise ValueError("Cluster count exceeds distinct sampled inputs")
        if params.affinity == "nearest_neighbors" and params.neighbors >= rows:
            raise ValueError(
                "Spectral clustering needs more sampled rows than neighbors"
            )
