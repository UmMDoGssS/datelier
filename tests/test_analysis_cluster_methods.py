"""Additional clustering methods group separated data and retain row identity."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from sklearn.metrics import adjusted_rand_score

from datelier.analysis.cluster_colors import predict_clusters
from datelier.analysis.input import prepare_input
from datelier.analysis.parameters import EXTRA_DEFAULTS
from datelier.analysis.runner import run_analysis
from datelier.analysis.types import LIMITS, Algorithm, AnalysisRequest, ClusteringResult
from datelier.io.importing import load_file

METHODS = [
    Algorithm.MINIBATCH_KMEANS,
    Algorithm.GAUSSIAN_MIXTURE,
    Algorithm.BAYESIAN_MIXTURE,
    Algorithm.AGGLOMERATIVE,
    Algorithm.BIRCH,
    Algorithm.MEAN_SHIFT,
    Algorithm.SPECTRAL_CLUSTERING,
    Algorithm.AFFINITY_PROPAGATION,
]


@pytest.mark.parametrize("algorithm", METHODS)
def test_clusters_group_separated_blobs_and_preserve_sampled_ids(
    tmp_path: Path, algorithm: Algorithm
) -> None:
    rng = np.random.default_rng(19)
    truth = np.repeat(np.arange(3), 40)
    values = rng.normal(0, 0.08, (120, 3)) + np.eye(3)[truth] * 8
    path = tmp_path / "data.parquet"
    pl.DataFrame(values, schema=["x", "y", "z"]).write_parquet(path)
    dataset = load_file(path).dataset
    request = AnalysisRequest(("x", "y", "z"), EXTRA_DEFAULTS[algorithm], row_limit=100)
    prepared = prepare_input(dataset, request)
    result = run_analysis(prepared)
    assert isinstance(result, ClusteringResult)
    assert result.revision == dataset.revision
    assert result.provenance.request == request
    np.testing.assert_array_equal(result.row_ids, prepared.row_ids)
    assert sum(result.counts) + result.noise_count == len(prepared.row_ids)
    assert not result.labels.flags.writeable
    if algorithm == Algorithm.SPECTRAL_CLUSTERING:
        assert any(
            name == "Fit warning" and "not fully connected" in message
            for name, message in result.details
        )
    if algorithm == Algorithm.AFFINITY_PROPAGATION:
        # Exemplar clustering may split a blob; each group should remain pure.
        fitted_truth = truth[prepared.row_ids]
        assert all(
            len(set(fitted_truth[result.labels == label])) == 1
            for label in set(result.labels)
        )
    else:
        assert adjusted_rand_score(truth[prepared.row_ids], result.labels) > 0.9
    again = run_analysis(prepared)
    assert isinstance(again, ClusteringResult)
    np.testing.assert_array_equal(again.labels, result.labels)
    positions = np.arange(120, dtype=np.uint64)
    labels = predict_clusters(dataset, positions, result)
    if algorithm == Algorithm.MINIBATCH_KMEANS:
        assert result.fit is not None
        assert adjusted_rand_score(truth, labels) > 0.9
    else:
        assert result.fit is None
        assert np.count_nonzero(labels == -2) == 20
        np.testing.assert_array_equal(labels[result.row_ids], result.labels)
    with pytest.raises(ValueError, match="bounds"):
        replace(request, row_limit=LIMITS[algorithm] + 1).validate()


@pytest.mark.parametrize(
    "algorithm",
    [
        a
        for a in METHODS
        if a not in (Algorithm.MEAN_SHIFT, Algorithm.AFFINITY_PROPAGATION)
    ],
)
def test_requested_clusters_cannot_exceed_distinct_inputs(
    tmp_path: Path, algorithm: Algorithm
) -> None:
    path = tmp_path / "data.csv"
    path.write_text("x,y\n0,1\n0,1\n2,3\n2,3\n")
    with pytest.raises(ValueError, match="distinct"):
        prepare_input(
            load_file(path).dataset,
            AnalysisRequest(("x", "y"), EXTRA_DEFAULTS[algorithm], row_limit=100),
        )
