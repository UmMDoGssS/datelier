"""AffinityPropagationAlgorithm: parameter ownership, fitting and input constraints."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import ClusterEstimator, ClusteringAlgorithm
from datelier.analysis.parameter_fields import setting

if TYPE_CHECKING:
    from datelier.analysis.types import PreparedInput


@dataclass(frozen=True)
class AffinityPropagationAlgorithm(ClusteringAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.AFFINITY_PROPAGATION
    damping: float = setting(0.7, "Damping", 0.5, 0.999999)
    iterations: int = setting(300, "Iterations", 1, 10000)
    convergence_iterations: int = setting(15, "Convergence window", 1, 10000)
    automatic_preference: bool = field(
        default=True, metadata={"label": "Automatic preference"}
    )
    preference: float = field(
        default=-1.0,
        metadata={
            "label": "Preference",
            "min": -1000000000000.0,
            "max": 1000000000000.0,
            "when": ("automatic_preference", False),
        },
    )
    recipe_kind: ClassVar[str] = "AffinityPropagationParameters"
    row_limit: ClassVar[int] = 2000
    default_row_limit: ClassVar[int] = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import AffinityPropagation

        request = prepared.request
        values = prepared.values
        seed = request.seed
        estimator = AffinityPropagation(
            damping=self.damping,
            max_iter=self.iterations,
            convergence_iter=self.convergence_iterations,
            preference=None if self.automatic_preference else self.preference,
            random_state=seed,
        )
        return (estimator, values, ())

    def diagnostics(
        self, estimator: ClusterEstimator, labels: NDArray[np.int64]
    ) -> tuple[tuple[str, str], ...]:
        if np.all(labels < 0):
            raise ValueError(
                "Affinity propagation found no assignments; "
                "adjust damping, preference or iterations"
            )
        return ()
