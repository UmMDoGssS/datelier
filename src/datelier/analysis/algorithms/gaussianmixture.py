"""GaussianMixtureAlgorithm: parameter ownership, fitting and input constraints."""

from typing import Literal, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import ClusterEstimator, ClusteringAlgorithm
from datelier.analysis.parameters import GaussianMixtureParameters
from datelier.analysis.types import AnalysisRequest, PreparedInput


class GaussianMixtureAlgorithm(ClusteringAlgorithm[GaussianMixtureParameters]):
    parameter_type = GaussianMixtureParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.mixture import GaussianMixture

        request = prepared.request
        values = prepared.values
        params = self.parameters
        _dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        estimator = GaussianMixture(
            n_components=params.clusters,
            covariance_type=cast(
                Literal["full", "tied", "diag", "spherical"], params.covariance
            ),
            reg_covar=params.regularization,
            n_init=params.initializations,
            max_iter=params.iterations,
            random_state=seed,
        )
        return (estimator, values, tuple(details))

    def diagnostics(
        self, estimator: ClusterEstimator, labels: NDArray[np.int64]
    ) -> tuple[tuple[str, str], ...]:
        from sklearn.mixture import GaussianMixture

        estimator = cast(GaussianMixture, estimator)
        details: list[tuple[str, str]] = []
        details += [
            ("Converged", str(estimator.converged_)),
            ("Completed iterations", str(estimator.n_iter_)),
            ("Lower bound", f"{estimator.lower_bound_:.6g}"),
        ]
        return tuple(details)

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        params = self.parameters
        rows, width = values.shape
        if params.clusters > len(np.unique(values, axis=0)):
            raise ValueError("Cluster count exceeds distinct sampled inputs")
