"""MeanShiftAlgorithm: parameter ownership, fitting and input constraints."""

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import ClusterEstimator, ClusteringAlgorithm
from datelier.analysis.parameters import MeanShiftParameters
from datelier.analysis.types import PreparedInput


class MeanShiftAlgorithm(ClusteringAlgorithm[MeanShiftParameters]):
    parameter_type = MeanShiftParameters

    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.cluster import MeanShift, estimate_bandwidth
        from threadpoolctl import threadpool_limits

        request = prepared.request
        values = prepared.values
        params = self.parameters
        _dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        with threadpool_limits(limits=1):
            bandwidth = (
                float(
                    estimate_bandwidth(
                        prepared.values,
                        quantile=params.quantile,
                        n_samples=min(500, len(prepared.row_ids)),
                        random_state=seed,
                        n_jobs=1,
                    )
                )
                if params.automatic_bandwidth
                else params.bandwidth
            )
        if not np.isfinite(bandwidth) or bandwidth <= 0:
            raise ValueError(
                "Estimated bandwidth is zero; choose a positive manual bandwidth"
            )
        details.append(("Fitted bandwidth", f"{bandwidth:.6g}"))
        estimator = MeanShift(
            bandwidth=bandwidth,
            cluster_all=params.cluster_all,
            max_iter=params.iterations,
            n_jobs=1,
        )
        return (estimator, values, tuple(details))
