"""AffinityPropagationAlgorithm: parameter ownership, fitting and input constraints."""

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import ClusterEstimator, ClusteringAlgorithm
from datelier.analysis.parameters import AffinityPropagationParameters
from datelier.analysis.types import PreparedInput


class AffinityPropagationAlgorithm(ClusteringAlgorithm[AffinityPropagationParameters]):
    parameter_type = AffinityPropagationParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import AffinityPropagation

        request = prepared.request
        values = prepared.values
        params = self.parameters
        _dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        estimator = AffinityPropagation(
            damping=params.damping,
            max_iter=params.iterations,
            convergence_iter=params.convergence_iterations,
            preference=None if params.automatic_preference else params.preference,
            random_state=seed,
        )
        return (estimator, values, tuple(details))

    def diagnostics(
        self, estimator: ClusterEstimator, labels: NDArray[np.int64]
    ) -> tuple[tuple[str, str], ...]:
        if np.all(labels < 0):
            raise ValueError(
                "Affinity propagation found no assignments; "
                "adjust damping, preference or iterations"
            )
        return ()
