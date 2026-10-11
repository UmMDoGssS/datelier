"""SpectralClusteringAlgorithm: parameter ownership, fitting and input constraints."""

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
class SpectralClusteringAlgorithm(ClusteringAlgorithm):
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
            "min": 1e-09,
            "max": 1000000.0,
            "when": ("affinity", "rbf"),
        },
    )
    initializations: int = setting(10, "Initializations", 1, 100)
    recipe_kind: ClassVar[str] = "SpectralClusteringParameters"
    row_limit: ClassVar[int] = 3000
    default_row_limit: ClassVar[int] = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import SpectralClustering

        request = prepared.request
        values = prepared.values
        seed = request.seed
        estimator = SpectralClustering(
            n_clusters=self.clusters,
            affinity=self.affinity,
            n_neighbors=self.neighbors if self.affinity == "nearest_neighbors" else 10,
            gamma=self.gamma if self.affinity == "rbf" else 1.0,
            n_init=self.initializations,
            random_state=seed,
            n_jobs=1,
        )
        return (estimator, values, ())

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        if self.clusters > len(np.unique(values, axis=0)):
            raise ValueError("Cluster count exceeds distinct sampled inputs")
        if self.affinity == "nearest_neighbors" and self.neighbors >= len(values):
            raise ValueError(
                "Spectral clustering needs more sampled rows than neighbors"
            )


# Legacy recipe/import name refers to this same algorithm, not a second record.
SpectralClusteringParameters = SpectralClusteringAlgorithm
