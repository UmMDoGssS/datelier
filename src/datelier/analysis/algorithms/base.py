"""Typed algorithm families; fitted estimators stay inside the analysis worker."""

from abc import ABC, abstractmethod
from dataclasses import fields
from time import perf_counter
from typing import Protocol, cast
from warnings import catch_warnings

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.embedding_result import embedding_result
from datelier.analysis.parameters import validate_parameters
from datelier.analysis.provenance import make_provenance
from datelier.analysis.types import (
    AnalysisRequest,
    AnalysisResult,
    ClusteringResult,
    EmbeddingResult,
    KMeansFit,
    Parameters,
    PreparedInput,
)

type Details = tuple[tuple[str, str], ...]


class EmbeddingEstimator(Protocol):
    def fit_transform(self, X: NDArray[np.float64]) -> object: ...


class ClusterEstimator(Protocol):
    def fit_predict(self, X: NDArray[np.float64]) -> object: ...


class Algorithm[P: Parameters](ABC):
    parameter_type: type[P]

    def __init__(self, parameters: P) -> None:
        self.parameters = parameters

    @property
    def schema(self) -> tuple[object, ...]:
        return fields(self.parameters)

    def validate(self) -> None:
        validate_parameters(self.parameters)

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        return None

    @abstractmethod
    def run(self, prepared: PreparedInput) -> AnalysisResult:
        """Fit explicitly prepared data, preserving row identity and provenance."""


class DecompositionAlgorithm[P: Parameters](Algorithm[P], ABC):
    @abstractmethod
    def run(self, prepared: PreparedInput) -> EmbeddingResult: ...


class FittedDecompositionAlgorithm[P: Parameters](DecompositionAlgorithm[P], ABC):
    @abstractmethod
    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], Details]: ...

    def diagnostics(self, estimator: EmbeddingEstimator) -> Details:
        return ()

    def run(self, prepared: PreparedInput) -> EmbeddingResult:
        from threadpoolctl import threadpool_limits

        started = perf_counter()
        estimator, values, details = self.build(prepared)
        with catch_warnings(record=True) as captured, threadpool_limits(limits=1):
            coordinates = cast(
                NDArray[np.float64], estimator.fit_transform(values)
            ).astype(np.float64)
        return embedding_result(
            prepared,
            coordinates,
            started,
            (
                *details,
                *self.diagnostics(estimator),
                *(("Fit warning", str(w.message)) for w in captured),
            ),
        )


class ClusteringAlgorithm[P: Parameters](Algorithm[P], ABC):
    @abstractmethod
    def build(
        self, prepared: PreparedInput
    ) -> tuple[ClusterEstimator, NDArray[np.float64], Details]: ...

    def diagnostics(
        self, estimator: ClusterEstimator, labels: NDArray[np.int64]
    ) -> Details:
        return ()

    def fitted_centers(
        self, estimator: ClusterEstimator, prepared: PreparedInput
    ) -> KMeansFit | None:
        return None

    @staticmethod
    def center_fit(
        prepared: PreparedInput, centers: object, inertia: float
    ) -> KMeansFit:
        values = np.asarray(centers, dtype=np.float64)
        if not np.isfinite(values).all() or not np.isfinite(inertia):
            raise ValueError("Clustering overflow; enable standardization")
        values.flags.writeable = False
        return KMeansFit(prepared.model, values, inertia)

    def run(self, prepared: PreparedInput) -> ClusteringResult:
        from threadpoolctl import threadpool_limits

        started = perf_counter()
        estimator, values, details = self.build(prepared)
        with catch_warnings(record=True) as captured, threadpool_limits(limits=1):
            labels = cast(NDArray[np.int64], estimator.fit_predict(values)).astype(
                np.int64
            )
        if labels.shape != (len(prepared.row_ids),) or np.any(labels < -1):
            raise ValueError("Analysis produced invalid cluster assignments")
        details = (*details, *self.diagnostics(estimator, labels))
        fit = self.fitted_centers(estimator, prepared)
        if fit is None:
            positive = labels >= 0
            labels[positive] = np.searchsorted(
                np.unique(labels[positive]), labels[positive]
            )
        counts = tuple(int(v) for v in np.bincount(labels[labels >= 0]))
        labels.flags.writeable = False
        return ClusteringResult(
            prepared.revision,
            prepared.row_ids,
            labels,
            make_provenance(prepared, started),
            counts,
            fit,
            int(np.count_nonzero(labels == -1)),
            (*details, *(("Fit warning", str(w.message)) for w in captured)),
        )
