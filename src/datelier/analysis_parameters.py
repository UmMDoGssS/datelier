"""Typed method settings; trusted field metadata drives small parameter forms."""

import math
from dataclasses import dataclass, field, fields
from typing import ClassVar, cast

from datelier.analysis_algorithm import Algorithm


def setting[T](default: T, label: str, minimum: float = 0, maximum: float = 1e6) -> T:
    return field(
        default=default, metadata={"label": label, "min": minimum, "max": maximum}
    )


def choice(default: str, label: str, values: tuple[str, ...]) -> str:
    return field(default=default, metadata={"label": label, "choices": values})


@dataclass(frozen=True)
class DBSCANParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.DBSCAN
    epsilon: float = setting(0.5, "Neighborhood radius", 1e-9)
    min_samples: int = setting(5, "Minimum neighbors", 2, 10000)
    metric: str = choice("euclidean", "Distance", ("euclidean", "manhattan"))


@dataclass(frozen=True)
class HDBSCANParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.HDBSCAN
    min_cluster_size: int = setting(5, "Minimum cluster size", 2, 10000)
    min_samples: int = setting(5, "Minimum neighbors", 2, 10000)
    selection: str = choice("eom", "Cluster selection", ("eom", "leaf"))
    allow_single_cluster: bool = field(
        default=False, metadata={"label": "Allow one cluster"}
    )


@dataclass(frozen=True)
class OPTICSParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.OPTICS
    min_samples: int = setting(5, "Minimum neighbors", 2, 10000)
    min_cluster_size: int = setting(5, "Minimum cluster size", 2, 10000)
    xi: float = setting(0.05, "Steepness threshold", 1e-6, 0.999999)
    metric: str = choice("euclidean", "Distance", ("euclidean", "manhattan"))


@dataclass(frozen=True)
class MiniBatchParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.MINIBATCH_KMEANS
    clusters: int = setting(3, "Clusters", 1, 256)
    batch_size: int = setting(1024, "Batch size", 1, 100000)
    initializations: int = setting(3, "Initializations", 1, 100)
    iterations: int = setting(100, "Iterations", 1, 10000)


@dataclass(frozen=True)
class GaussianMixtureParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.GAUSSIAN_MIXTURE
    clusters: int = setting(3, "Components", 1, 256)
    covariance: str = choice(
        "full", "Covariance", ("full", "tied", "diag", "spherical")
    )
    regularization: float = setting(1e-6, "Covariance regularization", 1e-12)
    initializations: int = setting(1, "Initializations", 1, 100)
    iterations: int = setting(100, "Iterations", 1, 10000)


@dataclass(frozen=True)
class BayesianMixtureParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.BAYESIAN_MIXTURE
    clusters: int = setting(3, "Maximum components", 1, 256)
    covariance: str = choice(
        "full", "Covariance", ("full", "tied", "diag", "spherical")
    )
    concentration: float = setting(1.0, "Weight concentration", 1e-9)
    regularization: float = setting(1e-6, "Covariance regularization", 1e-12)
    iterations: int = setting(100, "Iterations", 1, 10000)


@dataclass(frozen=True)
class AgglomerativeParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.AGGLOMERATIVE
    clusters: int = setting(3, "Clusters", 1, 256)
    linkage: str = choice("ward", "Linkage", ("ward", "complete", "average", "single"))


@dataclass(frozen=True)
class BirchParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.BIRCH
    clusters: int = setting(3, "Clusters", 1, 256)
    threshold: float = setting(0.5, "Subcluster radius", 1e-9)
    branching: int = setting(50, "Branching factor", 2, 1000)


@dataclass(frozen=True)
class MeanShiftParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.MEAN_SHIFT
    automatic_bandwidth: bool = field(
        default=True, metadata={"label": "Automatic bandwidth"}
    )
    bandwidth: float = field(
        default=1.0,
        metadata={
            "label": "Bandwidth",
            "min": 1e-9,
            "max": 1e6,
            "when": ("automatic_bandwidth", False),
        },
    )
    quantile: float = field(
        default=0.3,
        metadata={
            "label": "Bandwidth quantile",
            "min": 1e-6,
            "max": 1.0,
            "when": ("automatic_bandwidth", True),
        },
    )
    cluster_all: bool = field(
        default=True, metadata={"label": "Assign isolated points"}
    )
    iterations: int = setting(300, "Iterations", 1, 10000)


@dataclass(frozen=True)
class SpectralClusteringParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.SPECTRAL_CLUSTERING
    clusters: int = setting(3, "Clusters", 1, 256)
    affinity: str = choice(
        "nearest_neighbors", "Affinity", ("nearest_neighbors", "rbf")
    )
    neighbors: int = field(
        default=10,
        metadata={
            "label": "Neighbors",
            "min": 2,
            "max": 10000,
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
    initializations: int = setting(10, "Initializations", 1, 100)


@dataclass(frozen=True)
class AffinityPropagationParameters:
    algorithm: ClassVar[Algorithm] = Algorithm.AFFINITY_PROPAGATION
    damping: float = setting(0.7, "Damping", 0.5, 0.999999)
    iterations: int = setting(300, "Iterations", 1, 10000)
    convergence_iterations: int = setting(15, "Convergence window", 1, 10000)
    automatic_preference: bool = field(
        default=True, metadata={"label": "Automatic preference"}
    )
    preference: float = field(
        default=-1.0,
        metadata={
            "label": "Preference",
            "min": -1e12,
            "max": 1e12,
            "when": ("automatic_preference", False),
        },
    )


ExtraParameters = (
    DBSCANParameters
    | HDBSCANParameters
    | OPTICSParameters
    | MiniBatchParameters
    | GaussianMixtureParameters
    | BayesianMixtureParameters
    | AgglomerativeParameters
    | BirchParameters
    | MeanShiftParameters
    | SpectralClusteringParameters
    | AffinityPropagationParameters
)
EXTRA_DEFAULTS: dict[Algorithm, ExtraParameters] = {
    p.algorithm: p
    for p in (
        DBSCANParameters(),
        HDBSCANParameters(),
        OPTICSParameters(),
        MiniBatchParameters(),
        GaussianMixtureParameters(),
        BayesianMixtureParameters(),
        AgglomerativeParameters(),
        BirchParameters(),
        MeanShiftParameters(),
        SpectralClusteringParameters(),
        AffinityPropagationParameters(),
    )
}
EXTRA_LIMITS = {
    Algorithm.DBSCAN: 5000,
    Algorithm.HDBSCAN: 10000,
    Algorithm.OPTICS: 5000,
    Algorithm.MINIBATCH_KMEANS: 100000,
    Algorithm.GAUSSIAN_MIXTURE: 50000,
    Algorithm.BAYESIAN_MIXTURE: 50000,
    Algorithm.AGGLOMERATIVE: 5000,
    Algorithm.BIRCH: 100000,
    Algorithm.MEAN_SHIFT: 5000,
    Algorithm.SPECTRAL_CLUSTERING: 3000,
    Algorithm.AFFINITY_PROPAGATION: 2000,
}
EXTRA_DEFAULT_LIMITS = {
    a: min(limit, 10000 if limit >= 50000 else 2000)
    for a, limit in EXTRA_LIMITS.items()
}


def validate_parameters(parameters: object) -> None:
    # Only trusted local dataclasses are reflected, never user-provided types.
    if not isinstance(parameters, tuple(type(p) for p in EXTRA_DEFAULTS.values())):
        return
    for item in fields(parameters):
        value: object = getattr(parameters, item.name)
        metadata = item.metadata
        if "when" in metadata:
            name, active = cast(tuple[str, object], metadata["when"])
            if getattr(parameters, name) != active:
                continue
        expected = type(item.default)
        if expected in (int, bool, str) and type(value) is not expected:
            raise ValueError(f"{metadata['label']} has an invalid type")
        if "choices" in metadata:
            if value not in cast(tuple[str, ...], metadata["choices"]):
                raise ValueError(f"{metadata['label']} has an unsupported choice")
        elif "min" in metadata:
            low, high = float(metadata["min"]), float(metadata["max"])
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not low <= value <= high
            ):
                raise ValueError(
                    f"{metadata['label']} must be finite "
                    f"and between {low:g} and {high:g}"
                )
