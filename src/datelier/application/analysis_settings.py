"""Analysis drafts and explicit requests without rendering dependencies."""

from dataclasses import dataclass, field, replace

from datelier.analysis.algorithms.registry import ALGORITHMS
from datelier.analysis.jobs import AnalysisJobs
from datelier.analysis.schema import ParameterValue
from datelier.analysis.types import (
    Algorithm,
    AnalysisRequest,
    Parameters,
    Preprocessing,
)
from datelier.core.dataset import Dataset
from datelier.plotting.data import feature_columns


@dataclass
class AnalysisSettings:
    features: list[str] = field(default_factory=list)
    numeric: tuple[str, ...] = ()
    standardize: bool = True
    impute: bool = False
    dimensions: int = 2
    seed: int = 42
    error: str = ""
    parameters: dict[Algorithm, Parameters] = field(
        default_factory=lambda: {a: builder() for a, builder in ALGORITHMS.items()}
    )
    limits: dict[Algorithm, int] = field(
        default_factory=lambda: {
            a: builder.default_row_limit for a, builder in ALGORITHMS.items()
        }
    )

    def update(self, algorithm: Algorithm, name: str, value: ParameterValue) -> None:
        builder = self.parameters[algorithm]
        self.parameters[algorithm] = builder.with_parameter(name, value)

    def restore(self, request: AnalysisRequest) -> None:
        self.parameters[request.algorithm] = request.parameters
        self.limits[request.algorithm] = request.row_limit

    def bind(self, dataset: Dataset) -> None:
        self.numeric = feature_columns(dataset)
        self.features = [n for n in self.features if n in self.numeric]

    def request(self, algorithm: Algorithm) -> AnalysisRequest:
        return AnalysisRequest(
            tuple(self.features),
            self.parameters[algorithm],
            Preprocessing(self.standardize, self.impute),
            self.seed,
            self.limits[algorithm],
            self.dimensions,
        )

    def matches_result(self, request: AnalysisRequest) -> bool:
        current = self.request(request.algorithm)
        if request.algorithm.is_clustering:
            current = replace(current, dimensions=request.dimensions)
        return current == request

    def start(self, jobs: AnalysisJobs, dataset: Dataset, algorithm: Algorithm) -> None:
        try:
            jobs.request(dataset, self.request(algorithm))
            self.error = ""
        except ValueError as error:
            self.error = str(error)
