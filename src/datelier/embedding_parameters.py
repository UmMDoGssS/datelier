"""Typed linear and manifold view settings."""

from dataclasses import dataclass, field
from typing import ClassVar

from datelier.analysis_algorithm import Algorithm
from datelier.parameter_fields import choice, setting


@dataclass(frozen=True)
class SVDParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.SVD
    iterations: int = setting(5, "Power iterations", 1, 100)


@dataclass(frozen=True)
class ICAParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.ICA
    function: str = choice("logcosh", "Contrast function", ("logcosh", "exp", "cube"))
    iterations: int = setting(500, "Iterations", 1, 10000)
    tolerance: float = setting(1e-4, "Tolerance", 1e-12, 1.0)


@dataclass(frozen=True)
class FactorAnalysisParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.FACTOR_ANALYSIS
    rotation: str = choice("none", "Rotation", ("none", "varimax", "quartimax"))
    iterations: int = setting(1000, "Iterations", 1, 10000)
    tolerance: float = setting(0.01, "Tolerance", 1e-12, 1.0)


@dataclass(frozen=True)
class KernelPCAParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.KERNEL_PCA
    kernel: str = choice("rbf", "Kernel", ("rbf", "poly", "cosine", "linear"))
    gamma: float = field(
        default=1.0,
        metadata={
            "label": "Kernel gamma",
            "min": 1e-9,
            "max": 1e6,
            "unless": ("kernel", ("cosine", "linear")),
        },
    )
    degree: int = field(
        default=3,
        metadata={
            "label": "Polynomial degree",
            "min": 1,
            "max": 10,
            "when": ("kernel", "poly"),
        },
    )


@dataclass(frozen=True)
class NMFParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.NMF
    scaling: str = choice("minmax", "NMF input scaling", ("minmax", "none"))
    iterations: int = setting(500, "Iterations", 1, 10000)
    tolerance: float = setting(1e-4, "Tolerance", 1e-12, 1.0)


@dataclass(frozen=True)
class GaussianProjectionParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.GAUSSIAN_PROJECTION


@dataclass(frozen=True)
class SparseProjectionParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.SPARSE_PROJECTION
    density: float = setting(0.3, "Projection density", 1e-6, 1.0)


@dataclass(frozen=True)
class IsomapParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.ISOMAP
    neighbors: int = setting(15, "Neighbors", 2, 100)
    metric: str = choice("euclidean", "Distance", ("euclidean", "manhattan"))


@dataclass(frozen=True)
class MDSParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.MDS
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


@dataclass(frozen=True)
class SpectralEmbeddingParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.SPECTRAL_EMBEDDING
    affinity: str = choice(
        "nearest_neighbors", "Affinity", ("nearest_neighbors", "rbf")
    )
    neighbors: int = field(
        default=15,
        metadata={
            "label": "Neighbors",
            "min": 2,
            "max": 100,
            "when": ("affinity", "nearest_neighbors"),
        },
    )
    gamma: float = field(
        default=1.0,
        metadata={
            "label": "Kernel gamma",
            "min": 1e-9,
            "max": 1e6,
            "when": ("affinity", "rbf"),
        },
    )


@dataclass(frozen=True)
class LLEParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.LLE
    method: str = choice(
        "standard", "LLE method", ("standard", "modified", "hessian", "ltsa")
    )
    neighbors: int = setting(15, "Neighbors", 2, 100)
    regularization: float = field(
        default=0.001,
        metadata={
            "label": "Local regularization",
            "min": 1e-12,
            "max": 1.0,
            "when": ("method", "standard"),
        },
    )


EmbeddingParameters = (
    IsomapParameters
    | MDSParameters
    | SpectralEmbeddingParameters
    | LLEParameters
    | SVDParameters
    | ICAParameters
    | FactorAnalysisParameters
    | KernelPCAParameters
    | NMFParameters
    | GaussianProjectionParameters
    | SparseProjectionParameters
)
EMBEDDING_DEFAULTS: dict[Algorithm, EmbeddingParameters] = {
    p.algorithm: p
    for p in (
        IsomapParameters(),
        MDSParameters(),
        SpectralEmbeddingParameters(),
        LLEParameters(),
        SVDParameters(),
        ICAParameters(),
        FactorAnalysisParameters(),
        KernelPCAParameters(),
        NMFParameters(),
        GaussianProjectionParameters(),
        SparseProjectionParameters(),
    )
}
EMBEDDING_LIMITS = {
    Algorithm.ISOMAP: 3000,
    Algorithm.MDS: 2000,
    Algorithm.SPECTRAL_EMBEDDING: 5000,
    Algorithm.LLE: 2000,
    Algorithm.SVD: 100000,
    Algorithm.ICA: 50000,
    Algorithm.FACTOR_ANALYSIS: 50000,
    Algorithm.KERNEL_PCA: 3000,
    Algorithm.NMF: 50000,
    Algorithm.GAUSSIAN_PROJECTION: 100000,
    Algorithm.SPARSE_PROJECTION: 100000,
}
