"""Typed algorithm families; fitted estimators stay inside the analysis worker."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from time import perf_counter
from typing import TYPE_CHECKING, ClassVar, Protocol, Self, cast
from warnings import catch_warnings

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.schema import (
    Parameter,
    ParameterValue,
    parameter_schema,
    validate_parameters,
)

if TYPE_CHECKING:
    from datelier.analysis.types import (
        AnalysisRequest,
        AnalysisResult,
        ClusteringResult,
        EmbeddingResult,
        KMeansFit,
        PreparedInput,
    )
    from datelier.core import Dataset


type Details = tuple[tuple[str, str], ...]


class EmbeddingEstimator(Protocol):
    def fit_transform(self, X: NDArray[np.float64]) -> object: ...


class ClusterEstimator(Protocol):
    def fit_predict(self, X: NDArray[np.float64]) -> object: ...


class Algorithm(ABC):
    algorithm: ClassVar[AlgorithmId]
    recipe_kind: ClassVar[str]
    row_limit: ClassVar[int]
    default_row_limit: ClassVar[int]

    @property
    def schema(self) -> tuple[Parameter, ...]:
        return parameter_schema(self)

    def with_parameter(self, name: str, value: ParameterValue) -> Self:
        descriptor = next((item for item in self.schema if item.name == name), None)
        if descriptor is None:
            raise ValueError(f"Unknown algorithm parameter: {name}")
        descriptor.validate(value)
        values = {item.name: getattr(self, item.name) for item in self.schema}
        values[name] = value
        # Trusted schema names/values are validated before dynamic construction.
        constructor = cast(Callable[..., Self], type(self))
        return constructor(**values)

    def validate(self) -> None:
        validate_parameters(self)

    def validate_input(
        self, values: NDArray[np.float64], request: AnalysisRequest
    ) -> None:
        return None

    def same_configuration(self, other: Algorithm) -> bool:
        return (
            self.algorithm == other.algorithm
            and self.schema == other.schema
            and all(
                getattr(self, item.name) == getattr(other, item.name)
                for item in self.schema
            )
        )

    def check_input(self, prepared: PreparedInput) -> None:
        if not self.same_configuration(prepared.request.method):
            raise ValueError("Prepared request does not match the algorithm parameters")
        prepared.request.validate()

    @abstractmethod
    def fit(self, prepared: PreparedInput) -> AnalysisResult:
        """Fit explicitly prepared data, preserving row identity and provenance."""


class DecompositionAlgorithm(Algorithm, ABC):
    libraries: ClassVar[tuple[str, ...]] = (
        "numpy",
        "polars",
        "scikit-learn",
        "threadpoolctl",
    )

    @abstractmethod
    def build(
        self, prepared: PreparedInput
    ) -> tuple[EmbeddingEstimator, NDArray[np.float64], Details]: ...

    def diagnostics(self, estimator: EmbeddingEstimator) -> Details:
        return ()

    def fit(self, prepared: PreparedInput) -> EmbeddingResult:
        from threadpoolctl import threadpool_limits

        from datelier.analysis.embedding_result import embedding_result

        self.check_input(prepared)
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
            self.libraries,
        )


class ClusteringAlgorithm(Algorithm, ABC):
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

    def predict(
        self, dataset: Dataset, positions: NDArray[np.uint64], result: ClusteringResult
    ) -> NDArray[np.int64]:
        import polars as pl

        if not self.same_configuration(result.provenance.request.method):
            raise ValueError("Cluster predictor does not match the fitted parameters")
        if dataset.revision != result.revision or len(positions) > 10000:
            raise ValueError(
                "Cluster colors require current revision "
                "and at most 10,000 displayed rows"
            )
        fit = result.fit
        if fit is None:
            known = dict(
                zip(result.row_ids.tolist(), result.labels.tolist(), strict=True)
            )
            labels = np.array(
                [known.get(int(i), -2) for i in dataset.row_ids.gather(positions)],
                dtype=np.int64,
            )
            labels.flags.writeable = False
            return labels
        raw = pl.DataFrame(
            {
                f"f{i}": dataset.table.get_column(name)
                .gather(positions)
                .cast(pl.Float64)
                for i, name in enumerate(fit.model.features)
            }
        ).to_numpy()
        values, eligible = fit.model.transform(raw)
        if not fit.model.settings.impute:
            original_valid = np.ones(len(positions), dtype=bool)
            for name in result.provenance.input.removed_constants:
                original_valid &= (
                    dataset.table.get_column(name)
                    .gather(positions)
                    .cast(pl.Float64)
                    .is_finite()
                    .fill_null(False)
                    .to_numpy()
                )
            keep = original_valid[eligible]
            values = values[keep]
            eligible &= original_valid
        labels = np.full(len(positions), -2, dtype=np.int64)
        labels[eligible] = self.predict_values(values, fit)
        labels.flags.writeable = False
        return labels

    def predict_values(
        self, values: NDArray[np.float64], fit: KMeansFit
    ) -> NDArray[np.int64]:
        raise ValueError("This algorithm has no predictor for unseen rows")

    def fit(self, prepared: PreparedInput) -> ClusteringResult:
        from threadpoolctl import threadpool_limits

        from datelier.analysis.provenance import make_provenance
        from datelier.analysis.types import ClusteringResult

        self.check_input(prepared)
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


class NearestCenterClusteringAlgorithm(ClusteringAlgorithm, ABC):
    """K-means family predicts in the original fitted preprocessing space."""

    @staticmethod
    def center_fit(
        prepared: PreparedInput, centers: object, inertia: float
    ) -> KMeansFit:
        from datelier.analysis.types import KMeansFit

        values = np.asarray(centers, dtype=np.float64)
        if not np.isfinite(values).all() or not np.isfinite(inertia):
            raise ValueError("Clustering overflow; enable standardization")
        values.flags.writeable = False
        return KMeansFit(prepared.model, values, inertia)

    def predict_values(
        self, values: NDArray[np.float64], fit: KMeansFit
    ) -> NDArray[np.int64]:
        # Bounded n×k distances rather than n×k×features temporary copies.
        with np.errstate(over="ignore", invalid="ignore"):
            distances = (
                (values * values).sum(axis=1)[:, None]
                + (fit.centers * fit.centers).sum(axis=1)[None, :]
                - 2 * values @ fit.centers.T
            )
        if not np.isfinite(distances).all():
            raise ValueError("Cluster distance overflow; fit with standardization")
        return np.argmin(distances, axis=1)
