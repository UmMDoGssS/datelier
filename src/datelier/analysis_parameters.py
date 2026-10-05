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


ExtraParameters = DBSCANParameters | HDBSCANParameters | OPTICSParameters
EXTRA_DEFAULTS: dict[Algorithm, ExtraParameters] = {
    p.algorithm: p
    for p in (DBSCANParameters(), HDBSCANParameters(), OPTICSParameters())
}
EXTRA_LIMITS = {
    Algorithm.DBSCAN: 5000,
    Algorithm.HDBSCAN: 10000,
    Algorithm.OPTICS: 5000,
}
EXTRA_DEFAULT_LIMITS = {a: min(limit, 2000) for a, limit in EXTRA_LIMITS.items()}


def validate_parameters(parameters: object) -> None:
    # Only trusted local dataclasses are reflected, never user-provided types.
    if not isinstance(parameters, tuple(type(p) for p in EXTRA_DEFAULTS.values())):
        return
    for item in fields(parameters):
        value: object = getattr(parameters, item.name)
        metadata = item.metadata
        expected = type(item.default)
        if expected in (int, bool, str) and type(value) is not expected:
            raise ValueError(f"{metadata['label']} has an invalid type")
        if "choices" in metadata:
            if value not in cast(tuple[str, ...], metadata["choices"]):
                raise ValueError(f"{metadata['label']} has an unsupported choice")
        elif "min" in metadata:
            low, high = float(metadata["min"]), float(metadata["max"])
            if (
                not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not low <= value <= high
            ):
                raise ValueError(
                    f"{metadata['label']} must be finite "
                    f"and between {low:g} and {high:g}"
                )
