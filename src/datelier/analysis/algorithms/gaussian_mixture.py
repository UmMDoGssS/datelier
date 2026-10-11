"""GaussianMixtureAlgorithm: parameter ownership, fitting and input constraints."""

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
class GaussianMixtureParameters:
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.GAUSSIAN_MIXTURE
    clusters: int = setting(3, "Components", 1, 256)
    covariance: str = choice(
        "full", "Covariance", ("full", "tied", "diag", "spherical")
    )
    regularization: float = setting(1e-6, "Covariance regularization", 1e-12)
    initializations: int = setting(1, "Initializations", 1, 100)
    iterations: int = setting(100, "Iterations", 1, 10000)


class GaussianMixtureAlgorithm(ClusteringAlgorithm[GaussianMixtureParameters]):
    parameter_type = GaussianMixtureParameters
    row_limit = 50000
    default_row_limit = 10000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.mixture import GaussianMixture

        request = prepared.request
        values = prepared.values
        params = self.parameters
        seed = request.seed
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
        if params.clusters > len(np.unique(values, axis=0)):
            raise ValueError("Cluster count exceeds distinct sampled inputs")
