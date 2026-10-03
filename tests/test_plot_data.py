import numpy as np
import polars as pl
import pytest

from datelier.feasibility.fixtures import make_table
from datelier.feasibility.plot_data import prepare_scatter


def test_bounded_conversion_retains_filtered_row_identity() -> None:
    table = pl.DataFrame(
        {
            "row_id": [41, 9, 20, 8, 7],
            "x": [1.0, None, float("inf"), 4.0, 5.0],
            "y": [2.0, 3.0, 4.0, 6.0, 7.0],
        }
    )
    points = prepare_scatter(table, "x", "y", limit=2)
    assert points.row_ids.tolist() == [41, 8]
    assert points.x.tolist() == [1.0, 4.0]
    assert points.y.tolist() == [2.0, 6.0]
    assert points.x.dtype == np.float64
    assert points.eligible_rows == 3
    assert points.source_rows == 5
    assert table.height == 5


def test_empty_fixture_has_valid_empty_plot_arrays() -> None:
    points = prepare_scatter(make_table(0), "feature_0", "feature_1")
    assert points.x.shape == points.y.shape == points.row_ids.shape == (0,)


def test_fixture_is_deterministic_mixed_and_identified() -> None:
    table = make_table(100, 10)
    assert table.equals(make_table(100, 10))
    assert table.shape == (100, 12)
    assert table["row_id"].n_unique() == 100
    assert table["feature_9"].null_count() == 6
    assert table["category"].n_unique() == 3


def test_invalid_coordinate_and_limit_are_rejected() -> None:
    with pytest.raises(ValueError, match="numeric"):
        prepare_scatter(make_table(10), "category", "feature_0")
    with pytest.raises(ValueError, match="positive"):
        prepare_scatter(make_table(10), "feature_0", "feature_1", limit=0)
