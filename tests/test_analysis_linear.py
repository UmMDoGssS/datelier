"""Additional embedding methods produce finite, reproducible aligned views."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from datelier.analysis import run_analysis
from datelier.analysis_input import prepare_input
from datelier.analysis_types import (
    Algorithm,
    AnalysisRequest,
    EmbeddingResult,
    Preprocessing,
)
from datelier.embedding_parameters import EMBEDDING_DEFAULTS, NMFParameters
from datelier.importing import load_file


@pytest.mark.parametrize(
    "algorithm",
    [
        a
        for a in EMBEDDING_DEFAULTS
        if a
        not in (
            Algorithm.ISOMAP,
            Algorithm.MDS,
            Algorithm.SPECTRAL_EMBEDDING,
            Algorithm.LLE,
        )
    ],
)
@pytest.mark.parametrize("dimensions", [2, 3])
def test_linear_views_preserve_finite_coordinates_and_ids(
    tmp_path: Path, algorithm: Algorithm, dimensions: int
) -> None:
    rng = np.random.default_rng(42)
    values = rng.uniform(1, 10, (90, 5))
    values[0, 0] = np.nan
    path = tmp_path / "data.parquet"
    pl.DataFrame(values, schema=["a", "b", "c", "d", "e"]).write_parquet(path)
    dataset = load_file(path).dataset
    request = AnalysisRequest(
        tuple(dataset.table.columns),
        EMBEDDING_DEFAULTS[algorithm],
        row_limit=60,
        dimensions=dimensions,
    )
    prepared = prepare_input(dataset, request)
    before = prepared.values.copy()
    result = run_analysis(prepared)
    assert isinstance(result, EmbeddingResult)
    assert result.values.shape == (60, dimensions)
    assert np.isfinite(result.values).all()
    assert not result.values.flags.writeable
    assert 0 not in result.row_ids
    np.testing.assert_array_equal(result.row_ids, prepared.row_ids)
    np.testing.assert_array_equal(result.positions, prepared.positions)
    np.testing.assert_array_equal(prepared.values, before)
    assert result.provenance.request == request
    again = run_analysis(prepared)
    assert isinstance(again, EmbeddingResult)
    np.testing.assert_allclose(again.values, result.values, rtol=1e-6, atol=1e-6)
    if algorithm == Algorithm.NMF:
        assert np.all(result.values >= 0)
        assert any("[0, 1]" in value for _, value in result.details)


def test_nmf_requires_explicit_scaling_for_negative_inputs(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("a,b,c\n1,2,3\n4,5,6\n7,8,10\n")
    dataset = load_file(path).dataset
    request = AnalysisRequest(
        ("a", "b", "c"), NMFParameters(scaling="none"), row_limit=100
    )
    with pytest.raises(ValueError, match="nonnegative"):
        prepare_input(dataset, request)
    unscaled = replace(request, preprocessing=Preprocessing(standardize=False))
    result = run_analysis(prepare_input(dataset, unscaled))
    assert isinstance(result, EmbeddingResult) and np.all(result.values >= 0)


@pytest.mark.parametrize(
    "algorithm",
    [Algorithm.SVD, Algorithm.ICA, Algorithm.FACTOR_ANALYSIS, Algorithm.NMF],
)
def test_linear_dimension_constraints_fail_before_fit(
    tmp_path: Path, algorithm: Algorithm
) -> None:
    path = tmp_path / "data.csv"
    path.write_text("a,b\n1,2\n4,5\n7,9\n")
    with pytest.raises(ValueError, match="dimensions"):
        prepare_input(
            load_file(path).dataset,
            AnalysisRequest(
                ("a", "b"), EMBEDDING_DEFAULTS[algorithm], row_limit=100, dimensions=3
            ),
        )
