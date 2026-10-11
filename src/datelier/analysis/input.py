"""Polars-backed eligibility and source-ID sampling before the ML boundary."""

import numpy as np
import polars as pl

from datelier.analysis.algorithms.registry import build_algorithm
from datelier.analysis.types import (
    AnalysisRequest,
    InputSummary,
    PreparedInput,
    PreprocessingModel,
)
from datelier.core.dataset import Dataset
from datelier.core.sampling import seeded_sample
from datelier.plotting.data import numeric_columns


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
        (n for n, keep in zip(request.features, varying, strict=True) if not keep)
    )
    features = tuple(
        (n for n, keep in zip(request.features, varying, strict=True) if keep)
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
    rows = values.shape[0]
    build_algorithm(request.parameters).validate_input(values, request)
    ids, positions = (sample["id"].to_numpy(), sample["position"].to_numpy())
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
