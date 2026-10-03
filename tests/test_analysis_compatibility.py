import numpy as np
import polars as pl
import pytest

from datelier.feasibility.analysis import Algorithm, prepare_input, run_probe
from datelier.feasibility.fixtures import make_table


@pytest.mark.parametrize("algorithm", ["pca", "tsne", "umap", "kmeans"])
def test_tiny_analysis_is_finite_and_aligned(algorithm: Algorithm) -> None:
    table = make_table(64, 3)
    inputs = prepare_input(table)
    result = run_probe(algorithm, inputs)
    expected_ids = [row for row in range(64) if row % 17]
    assert result.row_ids.tolist() == expected_ids
    expected_shape = (60,) if algorithm == "kmeans" else (60, 2)
    assert result.values.shape == expected_shape
    assert np.isfinite(result.values).all()
    assert result.parameters["random_state"] == 42
    if algorithm == "kmeans":
        # Labels are arbitrary; each separated synthetic group must share one label.
        groups = [set(result.values[result.row_ids % 3 == group]) for group in range(3)]
        assert all(len(group) == 1 for group in groups)
        assert len(set.union(*groups)) == 3
    if algorithm == "pca":
        assert np.var(result.values[:, 0]) > np.var(result.values[:, 1]) * 10


def test_preprocessing_excludes_nonfinite_rows_without_reordering() -> None:
    table = make_table(32, 3).with_columns(
        pl.when(pl.col("row_id") == 5)
        .then(float("nan"))
        .otherwise(pl.col("feature_0"))
        .alias("feature_0")
    )
    inputs = prepare_input(table)
    assert inputs.row_ids.tolist() == [
        row for row in range(32) if row % 17 and row != 5
    ]
    assert np.isfinite(inputs.values).all()
    np.testing.assert_allclose(inputs.values.mean(axis=0), 0, atol=1e-12)


def test_too_few_eligible_rows_are_rejected() -> None:
    with pytest.raises(ValueError, match="eight finite rows"):
        prepare_input(make_table(5, 3))
