"""Density clustering preserves fit identities, noise, and bounded execution."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from datelier.analysis import run_analysis
from datelier.analysis_input import prepare_input
from datelier.analysis_parameters import (
    DBSCANParameters,
    HDBSCANParameters,
    OPTICSParameters,
)
from datelier.analysis_types import AnalysisRequest, ClusteringResult
from datelier.clustering import predict_clusters, prepare_cluster_colors
from datelier.io.importing import load_file


@pytest.mark.parametrize(
    "parameters",
    [
        DBSCANParameters(),
        HDBSCANParameters(),
        OPTICSParameters(min_cluster_size=20, xi=0.2),
    ],
)
def test_density_fits_keep_noise_separate_from_unseen_rows(
    tmp_path: Path,
    parameters: DBSCANParameters | HDBSCANParameters | OPTICSParameters,
) -> None:
    rng = np.random.default_rng(4)
    values = np.r_[
        rng.normal(-3, 0.08, (40, 3)),
        rng.normal(3, 0.08, (40, 3)),
        [[0, 100, 0]],
        [[np.nan, 0, 0]],
    ]
    path = tmp_path / "data.parquet"
    pl.DataFrame(values, schema=["x", "y", "z"]).write_parquet(path)
    dataset = load_file(path).dataset
    request = AnalysisRequest(("x", "y", "z"), parameters, row_limit=100)
    prepared = prepare_input(dataset, request)
    result = run_analysis(prepared)
    assert isinstance(result, ClusteringResult)
    assert result.fit is None
    assert result.noise_count == int(np.count_nonzero(result.labels == -1))
    if not isinstance(parameters, OPTICSParameters):
        assert result.noise_count >= 1
    assert result.row_ids.tolist() == list(range(81))
    assert sum(result.counts) + result.noise_count == 81
    assert not result.labels.flags.writeable
    assert len(set(result.labels[:40])) == 1
    assert len(set(result.labels[40:80])) == 1
    assert result.labels[0] != result.labels[40]
    if not isinstance(parameters, OPTICSParameters):
        assert result.labels[80] == -1
    positions = np.arange(82, dtype=np.uint64)
    labels = predict_clusters(dataset, positions, result)
    assert labels[-1] == -2
    assert labels[-2] == result.labels[-1]
    colors = prepare_cluster_colors(dataset, positions, result)
    if result.noise_count:
        noise_position = int(np.flatnonzero(labels == -1)[0])
        assert colors.rgba[noise_position] != colors.rgba[-1]
        assert any(name.startswith("Noise") for name, _ in colors.legend)
    assert any(name.startswith("Unassigned") for name, _ in colors.legend)
    again = run_analysis(prepared)
    assert isinstance(again, ClusteringResult)
    np.testing.assert_array_equal(result.labels, again.labels)
    sampled = run_analysis(prepare_input(dataset, replace(request, row_limit=30)))
    assert isinstance(sampled, ClusteringResult)
    aligned = predict_clusters(dataset, positions, sampled)
    assert np.count_nonzero(aligned == -2) == 82 - 30
    for row, label in zip(sampled.row_ids, sampled.labels, strict=True):
        assert aligned[row] == label


@pytest.mark.parametrize(
    "parameters",
    [
        DBSCANParameters(epsilon=float("nan")),
        DBSCANParameters(min_samples=0),
        HDBSCANParameters(min_cluster_size=1),
        OPTICSParameters(xi=1),
    ],
)
def test_density_rejects_invalid_settings(parameters: object) -> None:
    from typing import cast

    from datelier.analysis_types import Parameters

    with pytest.raises(ValueError):
        AnalysisRequest(("x",), cast(Parameters, parameters), row_limit=100).validate()
