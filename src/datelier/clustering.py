"""Cluster assignments and predictions for bounded displayed rows."""

import numpy as np
import polars as pl
from numpy.typing import NDArray

from datelier.analysis_types import ClusteringResult
from datelier.coloring import NEUTRAL, PALETTE, PointColors, color_series
from datelier.core.dataset import Dataset


def predict_clusters(
    dataset: Dataset, positions: NDArray[np.uint64], result: ClusteringResult
) -> NDArray[np.int64]:
    if dataset.revision != result.revision or len(positions) > 10_000:
        raise ValueError(
            "Cluster colors require current revision and at most 10,000 displayed rows"
        )
    fit = result.fit
    if fit is None:
        # A label-only clustering result colors known identities; unseen rows
        # remain excluded rather than inventing a prediction rule.
        known = dict(zip(result.row_ids.tolist(), result.labels.tolist(), strict=True))
        labels = np.array(
            [known.get(int(i), -2) for i in dataset.row_ids.gather(positions)],
            dtype=np.int64,
        )
        labels.flags.writeable = False
        return labels
    # Resolve literal names as Series, never as regex expressions.
    raw = pl.DataFrame(
        {
            f"f{i}": dataset.table.get_column(name).gather(positions).cast(pl.Float64)
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
    # Bounded n×k distances rather than n×k×features temporary copies.
    with np.errstate(over="ignore", invalid="ignore"):
        distances = (
            (values * values).sum(axis=1)[:, None]
            + (fit.centers * fit.centers).sum(axis=1)[None, :]
            - 2 * values @ fit.centers.T
        )
    if not np.isfinite(distances).all():
        raise ValueError("Cluster distance overflow; fit with standardization")
    labels[eligible] = np.argmin(distances, axis=1)
    labels.flags.writeable = False
    return labels


def prepare_cluster_colors(
    dataset: Dataset, positions: NDArray[np.uint64], result: ClusteringResult
) -> PointColors:
    labels = predict_clusters(dataset, positions, result)
    leading = sorted(range(len(result.counts)), key=lambda i: (-result.counts[i], i))[
        :12
    ]
    palette = {label: PALETTE[i] for i, label in enumerate(leading)}
    rgba = np.array(
        [
            0xFF7777DD
            if label == -1
            else NEUTRAL
            if label < 0
            else palette.get(int(label), 0xFFBBBBBB)
            for label in labels
        ],
        dtype=np.uint32,
    )
    rgba.flags.writeable = False
    fitted_ids = set(int(i) for i in result.row_ids)
    displayed_fit = sum(int(i) in fitted_ids for i in dataset.row_ids.gather(positions))
    legend = tuple(
        (f"Cluster {i} (fit {result.counts[i]:,})", palette[i]) for i in leading
    )
    extra = []
    if len(result.counts) > len(leading):
        extra.append(("Other clusters", 0xFFBBBBBB))
    if result.noise_count:
        extra.append((f"Noise (fit {result.noise_count:,})", 0xFF7777DD))
    if np.any(labels == -2):
        extra.append(("Unassigned / excluded", NEUTRAL))
    entries = (*legend, *extra)
    return PointColors(
        str(result.provenance.request.algorithm),
        rgba,
        entries,
        f"Fit on {len(result.row_ids):,} sampled rows; "
        + (
            "displayed labels are nearest-center "
            f"predictions ({displayed_fit:,} fitting rows shown). "
            "Original analysis feature space."
            if result.fit is not None
            else f"Labels shown for {displayed_fit:,} fitting rows; "
            "unseen rows have no assignment."
        ),
        color_series(rgba, entries),
    )
