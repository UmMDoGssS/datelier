"""Manifold variants retain linked rows and reject invalid neighborhoods."""

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from datelier.analysis import run_analysis
from datelier.analysis_input import prepare_input
from datelier.analysis_types import AnalysisRequest, EmbeddingResult
from datelier.embedding_parameters import (
    IsomapParameters,
    LLEParameters,
    MDSParameters,
    SpectralEmbeddingParameters,
)
from datelier.importing import load_file

PARAMETERS = [
    IsomapParameters(),
    MDSParameters(),
    MDSParameters(metric=False, initialization="classical_mds"),
    SpectralEmbeddingParameters(),
    SpectralEmbeddingParameters(affinity="rbf"),
    *[LLEParameters(method=m) for m in ("standard", "modified", "hessian", "ltsa")],
]


@pytest.mark.parametrize("parameters", PARAMETERS)
@pytest.mark.parametrize("dimensions", [2, 3])
def test_manifold_views_are_finite_and_aligned(
    tmp_path: Path,
    parameters: IsomapParameters
    | LLEParameters
    | MDSParameters
    | SpectralEmbeddingParameters,
    dimensions: int,
) -> None:
    rng = np.random.default_rng(42)
    values = rng.normal(size=(100, 5))
    values[0, 0] = np.nan
    path = tmp_path / "data.parquet"
    pl.DataFrame(values, schema=["a", "b", "c", "d", "e"]).write_parquet(path)
    dataset = load_file(path).dataset
    request = AnalysisRequest(
        tuple(dataset.table.columns), parameters, row_limit=80, dimensions=dimensions
    )
    prepared = prepare_input(dataset, request)
    result = run_analysis(prepared)
    assert isinstance(result, EmbeddingResult)
    assert result.values.shape == (80, dimensions) and np.isfinite(result.values).all()
    assert not result.values.flags.writeable
    np.testing.assert_array_equal(result.row_ids, prepared.row_ids)
    np.testing.assert_array_equal(result.positions, prepared.positions)
    assert result.provenance.request == request
    again = run_analysis(prepared)
    assert isinstance(again, EmbeddingResult)
    np.testing.assert_allclose(again.values, result.values, atol=1e-6, rtol=1e-6)


@pytest.mark.parametrize(
    "parameters",
    [
        IsomapParameters(neighbors=10),
        SpectralEmbeddingParameters(neighbors=10),
        LLEParameters(neighbors=10),
        LLEParameters(method="hessian", neighbors=9),
    ],
)
def test_invalid_neighborhoods_fail_before_fit(
    tmp_path: Path,
    parameters: IsomapParameters | SpectralEmbeddingParameters | LLEParameters,
) -> None:
    path = tmp_path / "data.csv"
    path.write_text("a,b,c\n1,2,3\n4,5,6\n7,9,10\n8,10,12\n9,12,14\n")
    with pytest.raises(ValueError, match="Neighbors|neighbors"):
        prepare_input(
            load_file(path).dataset,
            AnalysisRequest(("a", "b", "c"), parameters, row_limit=100, dimensions=3),
        )
