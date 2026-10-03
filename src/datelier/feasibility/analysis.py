"""Explicit tiny compatibility probes, independent of GUI startup."""

from dataclasses import dataclass
from time import perf_counter
from typing import Literal, cast

import numpy as np
import polars as pl
from numpy.typing import NDArray
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.preprocessing import StandardScaler
from umap import UMAP

Algorithm = Literal["pca", "tsne", "umap", "kmeans"]
FEATURES = ("feature_0", "feature_1", "feature_2")
SEED = 42


@dataclass(frozen=True)
class ProbeInput:
    values: NDArray[np.float64]
    row_ids: NDArray[np.uint64]


@dataclass(frozen=True)
class ProbeResult:
    algorithm: Algorithm
    values: NDArray[np.float64] | NDArray[np.float32] | NDArray[np.int32]
    row_ids: NDArray[np.uint64]
    elapsed_seconds: float
    parameters: dict[str, int | str]


def prepare_input(table: pl.DataFrame) -> ProbeInput:
    selected = table.select("row_id", *FEATURES).filter(
        pl.all_horizontal(pl.col(name).is_finite() for name in FEATURES)
    )
    if selected.height < 8:
        raise ValueError("Compatibility probes require at least eight finite rows")
    values = selected.select(pl.col(FEATURES).cast(pl.Float64)).to_numpy()
    # scikit-learn's dynamic estimator API returns an unparameterized array.
    scaled = cast(NDArray[np.float64], StandardScaler().fit_transform(values))
    return ProbeInput(scaled, selected["row_id"].cast(pl.UInt64).to_numpy())


def run_probe(algorithm: Algorithm, inputs: ProbeInput) -> ProbeResult:
    """Run only when explicitly called; fixed settings expose compatibility evidence."""
    parameters: dict[str, int | str] = {
        "random_state": SEED,
        "preprocessing": "standard scaling; exclude null/nonfinite feature rows",
    }
    started = perf_counter()
    values: NDArray[np.float64] | NDArray[np.float32] | NDArray[np.int32]
    if algorithm == "pca":
        parameters.update(n_components=2, svd_solver="full")
        values = cast(
            NDArray[np.float64],
            PCA(n_components=2, svd_solver="full", random_state=SEED).fit_transform(
                inputs.values
            ),
        )
    elif algorithm == "tsne":
        parameters.update(n_components=2, perplexity=5, max_iter=500, init="pca")
        values = cast(
            NDArray[np.float32],
            TSNE(
                n_components=2,
                perplexity=5,
                max_iter=500,
                init="pca",
                random_state=SEED,
                n_jobs=1,
            ).fit_transform(inputs.values),
        )
    elif algorithm == "umap":
        parameters.update(n_components=2, n_neighbors=5, n_epochs=100, n_jobs=1)
        values = cast(
            NDArray[np.float32],
            UMAP(
                n_components=2,
                n_neighbors=5,
                n_epochs=100,
                random_state=SEED,
                n_jobs=1,
            ).fit_transform(inputs.values),
        )
    else:
        parameters.update(n_clusters=3, n_init=10)
        values = cast(
            NDArray[np.int32],
            KMeans(n_clusters=3, n_init=10, random_state=SEED).fit_predict(
                inputs.values
            ),
        )
    return ProbeResult(
        algorithm, values, inputs.row_ids, perf_counter() - started, parameters
    )
