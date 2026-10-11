"""BayesianMixtureAlgorithm: parameter ownership, fitting and input constraints."""

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
class BayesianMixtureAlgorithm(ClusteringAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.BAYESIAN_MIXTURE
    clusters: int = setting(3, "Maximum components", 1, 256)
    covariance: str = choice(
        "full", "Covariance", ("full", "tied", "diag", "spherical")
    )
    concentration: float = setting(1.0, "Weight concentration", 1e-09)
    regularization: float = setting(1e-06, "Covariance regularization", 1e-12)
    iterations: int = setting(100, "Iterations", 1, 10000)
    recipe_kind: ClassVar[str] = "BayesianMixtureParameters"
    row_limit: ClassVar[int] = 50000
    default_row_limit: ClassVar[int] = 10000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.mixture import BayesianGaussianMixture

        request = prepared.request
        values = prepared.values
        seed = request.seed
        details: list[tuple[str, str]] = []
        estimator = BayesianGaussianMixture(
            n_components=self.clusters,
            covariance_type=cast(
                Literal["full", "tied", "diag", "spherical"], self.covariance
            ),
            weight_concentration_prior=self.concentration,
            reg_covar=self.regularization,
            max_iter=self.iterations,
            random_state=seed,
        )
        return (estimator, values, tuple(details))

    def diagnostics(
        self, estimator: ClusterEstimator, labels: NDArray[np.int64]
    ) -> tuple[tuple[str, str], ...]:
        from sklearn.mixture import BayesianGaussianMixture

        estimator = cast(BayesianGaussianMixture, estimator)
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
        if self.clusters > len(np.unique(values, axis=0)):
            raise ValueError("Cluster count exceeds distinct sampled inputs")
