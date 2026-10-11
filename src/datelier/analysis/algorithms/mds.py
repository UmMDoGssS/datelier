"MDSAlgorithm: parameter ownership, fitting and input constraints."

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import (
    EmbeddingEstimator,
    FittedDecompositionAlgorithm,
)
from datelier.analysis.parameter_fields import choice, setting

if TYPE_CHECKING:
    from datelier.analysis.types import AnalysisRequest, PreparedInput


@dataclass(frozen=True)
class MDSParameters:
    algorithm: ClassVar[AlgorithmId] = AlgorithmId.MDS
    metric: bool = field(default=True, metadata={"label": "Metric MDS"})
    initialization: str = choice(
        "random", "Initialization", ("random", "classical_mds")
    )
    initializations: int = field(
        default=4,
        metadata={
            "label": "Initializations",
            "min": 1,
            "max": 100,
            "when": ("initialization", "random"),
        },
    )
    iterations: int = setting(300, "Iterations", 1, 10000)
    tolerance: float = setting(1e-6, "Stress tolerance", 1e-12, 1.0)


class MDSAlgorithm(FittedDecompositionAlgorithm[MDSParameters]):
    parameter_type = MDSParameters
    row_limit = 2000
    default_row_limit = 2000

    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], tuple[tuple[str, str], ...]]:
        from sklearn.manifold import MDS

        request = prepared.request
        values = prepared.values
        params = self.parameters
        dims, seed = (request.dimensions, request.seed)
        details: list[tuple[str, str]] = []
        mds_constructor = cast(Callable[..., MDS], MDS)
        estimator = mds_constructor(
            n_components=dims,
            metric_mds=params.metric,
            init=params.initialization,
            n_init=params.initializations if params.initialization == "random" else 1,
            max_iter=params.iterations,
            eps=params.tolerance,
            random_state=seed,
            n_jobs=1,
            normalized_stress="auto",
        )
        return (estimator, values, tuple(details))

    def diagnostics(self, estimator: EmbeddingEstimator) -> tuple[tuple[str, str], ...]:
        from sklearn.manifold import MDS

        estimator = cast(MDS, estimator)
        details: list[tuple[str, str]] = []
        details += [
            ("Stress", f"{estimator.stress_:.6g}"),
            ("Completed iterations", str(estimator.n_iter_)),
        ]
        return tuple(details)

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        rows, width = values.shape
        if rows <= request.dimensions:
            raise ValueError("MDS needs more sampled rows than dimensions")
