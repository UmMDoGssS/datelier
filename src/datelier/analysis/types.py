"""Typed requests and revision-bound analysis results; no GUI dependencies."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as Algorithm
from datelier.analysis.algorithms import ALGORITHMS, AlgorithmInstance
from datelier.analysis.algorithms.clustering import KMeansAlgorithm
from datelier.analysis.algorithms.decomposition import PCAAlgorithm
from datelier.analysis.algorithms.manifold import TSNEAlgorithm, UMAPAlgorithm
from datelier.core.dataset import DatasetRevision

# Compatibility imports refer to executable algorithm classes, not parameter records.
PCAParameters = PCAAlgorithm
KMeansParameters = KMeansAlgorithm
TSNEParameters = TSNEAlgorithm
UMAPParameters = UMAPAlgorithm
Parameters = AlgorithmInstance
LIMITS = {a: builder.row_limit for a, builder in ALGORITHMS.items()}
DEFAULT_LIMITS = {a: builder.default_row_limit for a, builder in ALGORITHMS.items()}


@dataclass(frozen=True)
class Preprocessing:
    standardize: bool = True
    impute: bool = False


@dataclass(frozen=True)
class AnalysisRequest:
    features: tuple[str, ...]
    parameters: AlgorithmInstance = PCAAlgorithm()
    preprocessing: Preprocessing = Preprocessing()
    seed: int = 42
    row_limit: int = 10_000
    dimensions: int = 2

    @property
    def method(self) -> AlgorithmInstance:
        """The executable algorithm; parameters is the preserved recipe field name."""
        return self.parameters

    @property
    def algorithm(self) -> Algorithm:
        return self.method.algorithm

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
        if type(self.method) is not ALGORITHMS[self.algorithm]:
            raise ValueError("Algorithm is not registered")
        self.method.validate()


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
    noise_count: int = 0
    details: tuple[tuple[str, str], ...] = ()


AnalysisResult = EmbeddingResult | ClusteringResult
