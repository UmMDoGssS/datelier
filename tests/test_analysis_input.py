from pathlib import Path

import numpy as np
import polars as pl
import pytest

from datelier.analysis_input import prepare_input
from datelier.analysis_types import (
    AnalysisRequest,
    KMeansParameters,
    Preprocessing,
    TSNEParameters,
    UMAPParameters,
)
from datelier.dataset import Dataset, SourceReference


def data(table: pl.DataFrame) -> Dataset:
    return Dataset.from_source(table, SourceReference(Path("unused"), 0, 0))


def test_preprocessing_identity_exclusions_and_constants() -> None:
    dataset = data(
        pl.DataFrame(
            {
                "^x$": [1.0, 2.0, None, 4.0, float("inf")],
                "y": [2.0, 3.0, 4.0, 6.0, 9.0],
                "constant": [3] * 5,
            }
        )
    )
    request = AnalysisRequest(("^x$", "y", "constant"))
    prepared = prepare_input(dataset, request)
    assert prepared.row_ids.tolist() == [0, 1, 3]
    assert prepared.summary.excluded_rows == 2
    assert prepared.summary.removed_constants == ("constant",)
    np.testing.assert_allclose(prepared.values.mean(axis=0), 0, atol=1e-15)
    np.testing.assert_allclose(prepared.values.std(axis=0), 1)
    assert not prepared.values.flags.writeable
    imputed = prepare_input(
        dataset,
        AnalysisRequest(request.features, preprocessing=Preprocessing(impute=True)),
    )
    assert imputed.summary.imputed_cells == 2 and len(imputed.values) == 5
    assert np.isfinite(imputed.values).all()


def test_sampling_stable_after_sort_and_prediction_transform() -> None:
    dataset = data(pl.DataFrame({"x": range(3000), "y": np.sin(np.arange(3000))}))
    request = AnalysisRequest(("x", "y"), row_limit=100)
    first = prepare_input(dataset, request)
    reverse = dataset.with_rows(dataset.table.reverse(), dataset.row_ids.reverse())
    second = prepare_input(reverse, request)
    np.testing.assert_array_equal(first.row_ids, second.row_ids)
    np.testing.assert_array_equal(first.values, second.values)
    raw = dataset.table[first.positions].to_numpy()
    predicted, valid = first.model.transform(raw)
    assert valid.all()
    np.testing.assert_allclose(predicted, first.values)


@pytest.mark.parametrize(
    "settings",
    [
        AnalysisRequest(("x", "x")),
        AnalysisRequest(("missing",)),
        AnalysisRequest(("x", "y"), row_limit=100001),
        AnalysisRequest(("x", "y"), TSNEParameters(perplexity=30)),
        AnalysisRequest(("x", "y"), UMAPParameters(neighbors=15)),
        AnalysisRequest(("x", "y"), KMeansParameters(clusters=20)),
    ],
)
def test_invalid_parameters_are_rejected(settings: AnalysisRequest) -> None:
    with pytest.raises(ValueError):
        prepare_input(data(pl.DataFrame({"x": range(10), "y": range(10)})), settings)


def test_extreme_standardization_and_all_missing_rejection() -> None:
    prepared = prepare_input(
        data(pl.DataFrame({"x": [-1e308, 0.0, 1e308], "y": [1e308, 0.0, -1e308]})),
        AnalysisRequest(("x", "y")),
    )
    assert np.isfinite(prepared.values).all()
    with pytest.raises(ValueError, match="entirely missing"):
        prepare_input(
            data(pl.DataFrame({"x": [None] * 3}, schema={"x": pl.Float64})),
            AnalysisRequest(("x",), preprocessing=Preprocessing(impute=True)),
        )
