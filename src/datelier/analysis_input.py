"""Polars-backed eligibility and source-ID sampling before the ML boundary."""

import numpy as np
import polars as pl

from datelier.analysis_parameters import (
    AgglomerativeParameters,
    BayesianMixtureParameters,
    BirchParameters,
    GaussianMixtureParameters,
    HDBSCANParameters,
    MiniBatchParameters,
    OPTICSParameters,
    SpectralClusteringParameters,
)
from datelier.analysis_types import (
    AnalysisRequest,
    InputSummary,
    KMeansParameters,
    PCAParameters,
    PreparedInput,
    PreprocessingModel,
    TSNEParameters,
    UMAPParameters,
)
from datelier.core.dataset import Dataset
from datelier.core.sampling import seeded_sample
from datelier.embedding_parameters import (
    FactorAnalysisParameters,
    ICAParameters,
    IsomapParameters,
    KernelPCAParameters,
    LLEParameters,
    MDSParameters,
    NMFParameters,
    SpectralEmbeddingParameters,
    SVDParameters,
)
from datelier.plotting import numeric_columns


def prepare_input(dataset: Dataset, request: AnalysisRequest) -> PreparedInput:
    request.validate()
    if any(name not in numeric_columns(dataset) for name in request.features):
        raise ValueError("Analysis features must be existing numeric columns")
    table = dataset.table
    columns = {
        f"f{i}": table.get_column(name).cast(pl.Float64)
        for i, name in enumerate(request.features)
    }
    frame = pl.DataFrame(
        {
            **columns,
            "id": dataset.row_ids,
            "position": pl.int_range(0, table.height, dtype=pl.UInt64, eager=True),
        }
    )
    if not request.preprocessing.impute:
        frame = frame.filter(pl.all_horizontal(pl.col(n).is_finite() for n in columns))
    eligible_count = frame.height
    sample = seeded_sample(frame, request.row_limit, request.seed)
    if sample.height < 2:
        raise ValueError("Analysis needs at least two eligible sampled rows")
    matrix = sample.select(list(columns)).to_numpy().copy()
    finite = np.isfinite(matrix)
    if not finite.any(axis=0).all():
        raise ValueError(
            "Cannot estimate a median for an entirely missing sampled feature"
        )
    magnitudes = np.max(np.where(finite, np.abs(matrix), 0), axis=0)
    magnitudes[magnitudes == 0] = 1
    normalized = matrix / magnitudes
    medians = np.array(
        [np.median(normalized[finite[:, i], i]) for i in range(matrix.shape[1])]
    )
    imputed = int((~finite).sum())
    normalized[~finite] = np.broadcast_to(medians, matrix.shape)[~finite]
    varying = np.ptp(normalized, axis=0) > 0
    removed = tuple(
        n for n, keep in zip(request.features, varying, strict=True) if not keep
    )
    features = tuple(
        n for n, keep in zip(request.features, varying, strict=True) if keep
    )
    if not features:
        raise ValueError("No varying features remain after preprocessing")
    matrix = matrix[:, varying]
    normalized = normalized[:, varying]
    model = PreprocessingModel(
        features,
        request.preprocessing,
        magnitudes[varying],
        medians[varying],
        normalized.mean(axis=0),
        normalized.std(axis=0),
    )
    values, _ = model.transform(matrix)
    params = request.parameters
    rows, width = values.shape
    if isinstance(params, PCAParameters) and request.dimensions > min(rows, width):
        raise ValueError(
            "PCA dimensions exceed the sampled rows or varying feature count"
        )
    if isinstance(params, TSNEParameters):
        if params.perplexity >= rows:
            raise ValueError(
                "t-SNE perplexity must be smaller than the sampled row count"
            )
        if params.initialization == "pca" and request.dimensions > min(rows, width):
            raise ValueError(
                "PCA initialization needs enough varying features for the dimensions"
            )
    if isinstance(params, UMAPParameters):
        if params.neighbors >= rows or rows <= request.dimensions + 1:
            raise ValueError(
                "UMAP needs more sampled rows than neighbors and dimensions + 1"
            )
        if params.metric == "cosine" and np.any(np.linalg.norm(values, axis=1) == 0):
            raise ValueError(
                "Cosine distance is undefined for zero-valued preprocessed rows"
            )
    if isinstance(
        params,
        (
            KMeansParameters,
            MiniBatchParameters,
            GaussianMixtureParameters,
            BayesianMixtureParameters,
            AgglomerativeParameters,
            BirchParameters,
            SpectralClusteringParameters,
        ),
    ) and params.clusters > len(np.unique(values, axis=0)):
        raise ValueError("Cluster count exceeds distinct sampled inputs")
    if (
        isinstance(params, (HDBSCANParameters, OPTICSParameters))
        and max(params.min_samples, params.min_cluster_size) > rows
    ):
        raise ValueError("Minimum neighbors and cluster size exceed the sampled rows")
    if (
        isinstance(params, SpectralClusteringParameters)
        and params.affinity == "nearest_neighbors"
        and params.neighbors >= rows
    ):
        raise ValueError("Spectral clustering needs more sampled rows than neighbors")
    if isinstance(
        params, (SVDParameters, ICAParameters, FactorAnalysisParameters, NMFParameters)
    ) and request.dimensions > min(rows, width):
        raise ValueError(
            "Output dimensions exceed sampled rows or varying feature count"
        )
    if isinstance(params, SVDParameters) and width < 2:
        raise ValueError("Truncated SVD needs at least two varying features")
    if isinstance(params, KernelPCAParameters) and rows <= request.dimensions:
        raise ValueError("Kernel PCA needs more sampled rows than output dimensions")
    if (
        isinstance(params, NMFParameters)
        and params.scaling == "none"
        and np.any(values < 0)
    ):
        raise ValueError(
            "NMF needs nonnegative inputs; choose minmax scaling "
            "or disable standardization"
        )
    if isinstance(
        params, (IsomapParameters, LLEParameters, SpectralEmbeddingParameters)
    ):
        if rows <= request.dimensions + 1:
            raise ValueError(
                "Manifold views need more sampled rows than dimensions + 1"
            )
        uses_neighbors = (
            not isinstance(params, SpectralEmbeddingParameters)
            or params.affinity == "nearest_neighbors"
        )
        if uses_neighbors and params.neighbors >= rows:
            raise ValueError("Neighbors must be smaller than the sampled row count")
    if isinstance(params, MDSParameters) and rows <= request.dimensions:
        raise ValueError("MDS needs more sampled rows than dimensions")
    if isinstance(params, LLEParameters):
        if request.dimensions > width:
            raise ValueError("LLE dimensions exceed the varying feature count")
        minimum = (
            request.dimensions * (request.dimensions + 3) / 2
            if params.method == "hessian"
            else request.dimensions
        )
        if params.neighbors <= minimum:
            raise ValueError(
                f"{params.method} LLE needs more than {minimum:g} neighbors"
            )
    ids, positions = sample["id"].to_numpy(), sample["position"].to_numpy()
    for array in (
        values,
        ids,
        positions,
        model.magnitudes,
        model.medians,
        model.means,
        model.deviations,
    ):
        array.flags.writeable = False
    return PreparedInput(
        dataset.revision,
        request,
        values,
        ids,
        positions,
        InputSummary(
            table.height,
            eligible_count,
            table.height - eligible_count,
            rows,
            imputed,
            removed,
            features,
        ),
        model,
    )
