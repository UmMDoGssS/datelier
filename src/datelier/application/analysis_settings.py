"""Analysis drafts and explicit requests without rendering dependencies."""

from dataclasses import dataclass, field, replace

from datelier.analysis.jobs import AnalysisJobs
from datelier.analysis.parameters import (
    EXTRA_DEFAULT_LIMITS,
    EXTRA_DEFAULTS,
    ExtraParameters,
)
from datelier.analysis.types import (
    Algorithm,
    AnalysisRequest,
    KMeansParameters,
    PCAParameters,
    Preprocessing,
    TSNEParameters,
    UMAPParameters,
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
    pca_limit: int = 10_000
    pca_solver: int = 0
    pca_whiten: bool = False
    error: str = ""
    kmeans_limit: int = 10_000
    clusters: int = 3
    initializations: int = 10
    kmeans_iterations: int = 300
    center_index: int = 0
    tsne_limit: int = 2_000
    perplexity: float = 30
    tsne_iterations: int = 1_000
    tsne_auto_rate: bool = True
    tsne_rate: float = 200
    tsne_init: int = 0
    umap_limit: int = 5_000
    neighbors: int = 15
    min_distance: float = 0.1
    umap_metric: int = 0
    extra_parameters: dict[Algorithm, ExtraParameters] = field(
        default_factory=EXTRA_DEFAULTS.copy
    )
    extra_limits: dict[Algorithm, int] = field(
        default_factory=EXTRA_DEFAULT_LIMITS.copy
    )

    def bind(self, dataset: Dataset) -> None:
        self.numeric = feature_columns(dataset)
        self.features = [n for n in self.features if n in self.numeric]

    def request(self, algorithm: Algorithm) -> AnalysisRequest:
        if algorithm == Algorithm.PCA:
            params = PCAParameters(
                ["randomized", "full"][self.pca_solver], self.pca_whiten
            )
            limit = self.pca_limit
        elif algorithm == Algorithm.KMEANS:
            params = KMeansParameters(
                self.clusters, self.initializations, self.kmeans_iterations
            )
            limit = self.kmeans_limit
        elif algorithm == Algorithm.TSNE:
            params = TSNEParameters(
                self.perplexity,
                self.tsne_iterations,
                "auto" if self.tsne_auto_rate else self.tsne_rate,
                ["pca", "random"][self.tsne_init],
            )
            limit = self.tsne_limit
        elif algorithm == Algorithm.UMAP:
            params = UMAPParameters(
                self.neighbors,
                self.min_distance,
                ["euclidean", "cosine"][self.umap_metric],
            )
            limit = self.umap_limit
        else:
            params = self.extra_parameters[algorithm]
            limit = self.extra_limits[algorithm]
        return AnalysisRequest(
            tuple(self.features),
            params,
            Preprocessing(self.standardize, self.impute),
            self.seed,
            limit,
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
