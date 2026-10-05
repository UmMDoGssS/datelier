"""Typed requests and revision-bound analysis results; no GUI dependencies."""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

import numpy as np
from numpy.typing import NDArray

from datelier.dataset import DatasetRevision


class Algorithm(StrEnum):
    PCA = "PCA"
    TSNE = "t-SNE"
    UMAP = "UMAP"
    KMEANS = "K-means"

    @property
    def is_clustering(self) -> bool:
        return self == Algorithm.KMEANS


@dataclass(frozen=True)
class PCAParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.PCA
    solver: str = "randomized"
    whiten: bool = False


@dataclass(frozen=True)
class TSNEParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.TSNE
    perplexity: float = 30
    iterations: int = 1_000
    learning_rate: float | str = "auto"
    initialization: str = "pca"


@dataclass(frozen=True)
class UMAPParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.UMAP
    neighbors: int = 15
    min_distance: float = 0.1
    metric: str = "euclidean"


@dataclass(frozen=True)
class KMeansParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.KMEANS
    clusters: int = 3
    initializations: int = 10
    iterations: int = 300


Parameters = PCAParameters | TSNEParameters | UMAPParameters | KMeansParameters
LIMITS = {
    Algorithm.PCA: 100_000,
    Algorithm.KMEANS: 100_000,
    Algorithm.TSNE: 10_000,
    Algorithm.UMAP: 50_000,
}
DEFAULT_LIMITS = {
    Algorithm.PCA: 10_000,
    Algorithm.KMEANS: 10_000,
    Algorithm.TSNE: 2_000,
    Algorithm.UMAP: 5_000,
}


@dataclass(frozen=True)
class Preprocessing:
    standardize: bool = True
    impute: bool = False


@dataclass(frozen=True)
class AnalysisRequest:
    features: tuple[str, ...]
    parameters: Parameters = PCAParameters()
    preprocessing: Preprocessing = Preprocessing()
    seed: int = 42
    row_limit: int = 10_000
    dimensions: int = 2

    @property
    def algorithm(self) -> Algorithm:
        return self.parameters.algorithm

    def validate(self) -> None:
        if not 1 <= len(self.features) <= 128 or len(set(self.features)) != len(
            self.features
        ):
            raise ValueError("Choose 1–128 distinct numeric analysis features")
        if (
            not 0 <= self.seed <= 2**32 - 1
            or not 1 <= self.row_limit <= LIMITS[self.algorithm]
        ):
            raise ValueError(
                "Seed or sample limit exceeds the displayed analysis bounds"
            )
        if self.dimensions not in (2, 3):
            raise ValueError("Embedding dimensions must be two or three")
        params = self.parameters
        if isinstance(params, PCAParameters) and params.solver not in (
            "randomized",
            "full",
        ):
            raise ValueError("PCA solver must be randomized or full")
        if isinstance(params, TSNEParameters):
            if (
                not math.isfinite(params.perplexity)
                or params.perplexity <= 0
                or params.iterations < 250
            ):
                raise ValueError(
                    "t-SNE requires positive perplexity and at least 250 iterations"
                )
            if params.initialization not in ("pca", "random"):
                raise ValueError("t-SNE initialization must be pca or random")
            rate = params.learning_rate
            if rate != "auto" and (
                not isinstance(rate, (int, float))
                or not math.isfinite(rate)
                or rate <= 0
            ):
                raise ValueError(
                    "Learning rate must be auto or a positive finite number"
                )
        if isinstance(params, UMAPParameters):
            if (
                params.neighbors < 2
                or not math.isfinite(params.min_distance)
                or not 0 <= params.min_distance <= 1
            ):
                raise ValueError(
                    "UMAP needs at least two neighbors and minimum distance 0–1"
                )
            if params.metric not in ("euclidean", "cosine"):
                raise ValueError("UMAP metric must be euclidean or cosine")
        if (
            isinstance(params, KMeansParameters)
            and min(params.clusters, params.initializations, params.iterations) < 1
        ):
            raise ValueError(
                "Cluster count, initializations and iterations must be positive"
            )
        if isinstance(params, KMeansParameters) and params.clusters > 256:
            raise ValueError("Cluster count is capped at 256 for bounded coloring")


@dataclass(frozen=True)
class InputSummary:
    total_rows: int
    eligible_rows: int
    excluded_rows: int
    sampled_rows: int
    imputed_cells: int
    removed_constants: tuple[str, ...]
    used_features: tuple[str, ...]


@dataclass(frozen=True)
class PreprocessingModel:
    features: tuple[str, ...]
    settings: Preprocessing
    magnitudes: NDArray[np.float64]
    medians: NDArray[np.float64]
    means: NDArray[np.float64]
    deviations: NDArray[np.float64]

    def transform(
        self, values: NDArray[np.float64]
    ) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
        normalized = values / self.magnitudes
        finite = np.isfinite(normalized)
        eligible = (
            np.ones(len(values), dtype=np.bool_)
            if self.settings.impute
            else finite.all(axis=1)
        )
        normalized = normalized[eligible].copy()
        if self.settings.impute:
            invalid = ~np.isfinite(normalized)
            normalized[invalid] = np.broadcast_to(self.medians, normalized.shape)[
                invalid
            ]
        transformed = (
            (normalized - self.means) / self.deviations
            if self.settings.standardize
            else normalized * self.magnitudes
        )
        if not np.isfinite(transformed).all():
            raise ValueError("Preprocessed features overflow; enable standardization")
        return transformed, eligible


@dataclass(frozen=True)
class PreparedInput:
    revision: DatasetRevision
    request: AnalysisRequest
    values: NDArray[np.float64]
    row_ids: NDArray[np.uint64]
    positions: NDArray[np.uint64]
    summary: InputSummary
    model: PreprocessingModel


@dataclass(frozen=True)
class Provenance:
    request: AnalysisRequest
    input: InputSummary
    versions: tuple[tuple[str, str], ...]
    runtime_seconds: float


@dataclass(frozen=True)
class EmbeddingResult:
    revision: DatasetRevision
    row_ids: NDArray[np.uint64]
    positions: NDArray[np.uint64]
    values: NDArray[np.float64]
    provenance: Provenance
    details: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class KMeansFit:
    model: PreprocessingModel
    centers: NDArray[np.float64]
    inertia: float


@dataclass(frozen=True)
class ClusteringResult:
    revision: DatasetRevision
    row_ids: NDArray[np.uint64]
    labels: NDArray[np.int64]
    provenance: Provenance
    counts: tuple[int, ...]
    # Label-only results need no prediction capability or fitted centers.
    fit: KMeansFit | None = None


AnalysisResult = EmbeddingResult | ClusteringResult
