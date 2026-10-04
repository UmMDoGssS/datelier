"""Explicit, isolated estimator boundary with complete settings provenance."""

from importlib.metadata import version
from time import perf_counter
from typing import cast

import numpy as np
from numpy.typing import NDArray

from datelier.analysis_types import (
    AnalysisResult,
    EmbeddingResult,
    PCAParameters,
    PreparedInput,
    Provenance,
)


def run_analysis(prepared: PreparedInput) -> AnalysisResult:
    started = perf_counter()
    request = prepared.request
    params = request.parameters
    if not isinstance(params, PCAParameters):
        raise NotImplementedError(f"{request.algorithm} runner is not implemented yet")
    # Estimator imports stay inside the owned worker (never GUI import/startup).
    from sklearn.decomposition import PCA

    estimator = PCA(
        n_components=request.dimensions,
        svd_solver="full" if params.solver == "full" else "randomized",
        whiten=params.whiten,
        random_state=request.seed,
    )
    # Narrow cast at scikit-learn's dynamic estimator-array boundary.
    coordinates = cast(
        NDArray[np.float64], estimator.fit_transform(prepared.values)
    ).astype(np.float64)
    if (
        coordinates.shape != (len(prepared.row_ids), request.dimensions)
        or not np.isfinite(coordinates).all()
    ):
        raise ValueError("Analysis produced invalid coordinates")
    coordinates.flags.writeable = False
    provenance = Provenance(
        request,
        prepared.summary,
        tuple((name, version(name)) for name in ("numpy", "polars", "scikit-learn")),
        perf_counter() - started,
    )
    return EmbeddingResult(
        prepared.revision,
        prepared.row_ids,
        prepared.positions,
        coordinates,
        provenance,
        (
            (
                "Explained variance ratio",
                str(estimator.explained_variance_ratio_.tolist()),
            ),
        ),
    )
