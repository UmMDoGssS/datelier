"""Cluster assignments and predictions for bounded displayed rows."""

import numpy as np
from numpy.typing import NDArray

from datelier.analysis.algorithms.base import ClusteringAlgorithm
from datelier.analysis.types import ClusteringResult
from datelier.core.dataset import Dataset
from datelier.plotting.colors import NEUTRAL, PALETTE, PointColors, color_series


def predict_clusters(
    dataset: Dataset, positions: NDArray[np.uint64], result: ClusteringResult
) -> NDArray[np.int64]:
    builder = result.provenance.request.method
    if not isinstance(builder, ClusteringAlgorithm):
        raise ValueError("Cluster prediction requires a clustering algorithm")
    return builder.predict(dataset, positions, result)


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
