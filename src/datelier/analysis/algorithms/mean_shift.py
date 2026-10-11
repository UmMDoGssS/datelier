"""MeanShiftAlgorithm: parameter ownership, fitting and input constraints."""

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
class MeanShiftAlgorithm(ClusteringAlgorithm):
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.MEAN_SHIFT
    automatic_bandwidth: bool = field(
        default=True, metadata={"label": "Automatic bandwidth"}
    )
    bandwidth: float = field(
        default=1.0,
        metadata={
            "label": "Bandwidth",
            "min": 1e-09,
            "max": 1000000.0,
            "when": ("automatic_bandwidth", False),
        },
    )
    quantile: float = field(
        default=0.3,
        metadata={
            "label": "Bandwidth quantile",
            "min": 1e-06,
            "max": 1.0,
            "when": ("automatic_bandwidth", True),
        },
    )
    cluster_all: bool = field(
        default=True, metadata={"label": "Assign isolated points"}
    )
    iterations: int = setting(300, "Iterations", 1, 10000)
    recipe_kind: ClassVar[str] = "MeanShiftParameters"
    row_limit: ClassVar[int] = 5000
    default_row_limit: ClassVar[int] = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import MeanShift, estimate_bandwidth
        from threadpoolctl import threadpool_limits

        request = prepared.request
        values = prepared.values
        seed = request.seed
        details: list[tuple[str, str]] = []
        with threadpool_limits(limits=1):
            bandwidth = (
                float(
                    estimate_bandwidth(
                        prepared.values,
                        quantile=self.quantile,
                        n_samples=min(500, len(prepared.row_ids)),
                        random_state=seed,
                        n_jobs=1,
                    )
                )
                if self.automatic_bandwidth
                else self.bandwidth
            )
        if not np.isfinite(bandwidth) or bandwidth <= 0:
            raise ValueError(
                "Estimated bandwidth is zero; choose a positive manual bandwidth"
            )
        details.append(("Fitted bandwidth", f"{bandwidth:.6g}"))
        estimator = MeanShift(
            bandwidth=bandwidth,
            cluster_all=self.cluster_all,
            max_iter=self.iterations,
            n_jobs=1,
        )
        return (estimator, values, tuple(details))
