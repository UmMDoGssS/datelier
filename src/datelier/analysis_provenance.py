"""Shared fit provenance at the estimator boundary."""

from importlib.metadata import version
from time import perf_counter

from datelier.analysis_types import PreparedInput, Provenance


def make_provenance(
    prepared: PreparedInput,
    started: float,
    libraries: tuple[str, ...] = ("numpy", "polars", "scikit-learn", "threadpoolctl"),
) -> Provenance:
    return Provenance(
        prepared.request,
        prepared.summary,
        tuple((name, version(name)) for name in libraries),
        perf_counter() - started,
    )
