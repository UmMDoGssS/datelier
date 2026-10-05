"""Linear/factorization estimator boundary; imports and fitting stay in workers."""

from time import perf_counter
from typing import Literal, cast
from warnings import catch_warnings

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.embedding_parameters import (
    FactorAnalysisParameters,
    GaussianProjectionParameters,
    ICAParameters,
    KernelPCAParameters,
    NMFParameters,
    SparseProjectionParameters,
    SVDParameters,
)
from datelier.analysis.embedding_result import embedding_result
from datelier.analysis.types import EmbeddingResult, PreparedInput


def run_linear(prepared: PreparedInput) -> EmbeddingResult:
    from sklearn.decomposition import (
        NMF,
        FactorAnalysis,
        FastICA,
        KernelPCA,
        TruncatedSVD,
    )
    from sklearn.random_projection import (
        GaussianRandomProjection,
        SparseRandomProjection,
    )
    from threadpoolctl import threadpool_limits

    started = perf_counter()
    request, values = prepared.request, prepared.values
    params, dims, seed = request.parameters, request.dimensions, request.seed
    details: list[tuple[str, str]] = []
    if isinstance(params, SVDParameters):
        estimator = TruncatedSVD(
            n_components=dims, n_iter=params.iterations, random_state=seed
        )
    elif isinstance(params, ICAParameters):
        estimator = FastICA(
            n_components=dims,
            fun=cast(Literal["logcosh", "exp", "cube"], params.function),
            max_iter=params.iterations,
            tol=params.tolerance,
            random_state=seed,
            whiten="unit-variance",
        )
    elif isinstance(params, FactorAnalysisParameters):
        rotation = (
            None
            if params.rotation == "none"
            else cast(Literal["varimax", "quartimax"], params.rotation)
        )
        estimator = FactorAnalysis(
            n_components=dims,
            rotation=rotation,
            max_iter=params.iterations,
            tol=params.tolerance,
            random_state=seed,
        )
    elif isinstance(params, KernelPCAParameters):
        estimator = KernelPCA(
            n_components=dims,
            kernel=cast(Literal["rbf", "poly", "cosine", "linear"], params.kernel),
            gamma=params.gamma if params.kernel in ("rbf", "poly") else None,
            degree=params.degree if params.kernel == "poly" else 3,
            eigen_solver="arpack",
            random_state=seed,
            n_jobs=1,
        )
    elif isinstance(params, NMFParameters):
        if params.scaling == "minmax":
            normalized = values / np.abs(values).max(axis=0)
            low, high = normalized.min(axis=0), normalized.max(axis=0)
            values = (normalized - low) / (high - low)
            details.append(("NMF input", "Each fitted feature scaled to [0, 1]"))
        elif np.any(values < 0):
            raise ValueError(
                "NMF needs nonnegative inputs; choose minmax scaling "
                "or disable standardization on nonnegative data"
            )
        estimator = NMF(
            n_components=dims,
            init="nndsvda",
            max_iter=params.iterations,
            tol=params.tolerance,
            random_state=seed,
        )
    elif isinstance(params, GaussianProjectionParameters):
        estimator = GaussianRandomProjection(n_components=dims, random_state=seed)
    elif isinstance(params, SparseProjectionParameters):
        estimator = SparseRandomProjection(
            n_components=dims,
            density=params.density,
            dense_output=True,
            random_state=seed,
        )
    else:
        raise NotImplementedError(f"No linear runner for {request.algorithm}")
    with catch_warnings(record=True) as captured, threadpool_limits(limits=1):
        coordinates = cast(NDArray[np.float64], estimator.fit_transform(values)).astype(
            np.float64
        )
    if isinstance(estimator, TruncatedSVD):
        details.append(
            (
                "Explained variance ratio",
                str(estimator.explained_variance_ratio_.tolist()),
            )
        )
    if isinstance(estimator, FastICA):
        details.append(("Completed iterations", str(estimator.n_iter_)))
    if isinstance(estimator, FactorAnalysis):
        details.append(("Final log likelihood", f"{estimator.loglike_[-1]:.6g}"))
    if isinstance(estimator, KernelPCA):
        details.append(("Eigenvalues", str(estimator.eigenvalues_.tolist())))
    if isinstance(estimator, NMF):
        details += [
            ("Reconstruction error", f"{estimator.reconstruction_err_:.6g}"),
            ("Completed iterations", str(estimator.n_iter_)),
        ]
    details += [("Fit warning", str(w.message)) for w in captured]
    return embedding_result(prepared, coordinates, started, tuple(details))
