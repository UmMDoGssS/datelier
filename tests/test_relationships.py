from pathlib import Path

import numpy as np
import polars as pl
import pytest

from datelier.core.dataset import Dataset, SourceReference
from datelier.inspection.exploration import PlotSettings, prepare_dashboard


def test_matrix_symmetry_order_diagonals_and_identity() -> None:
    data = Dataset.from_source(
        pl.DataFrame({"a": range(200), "b": range(200, 0, -1), "constant": [1] * 200}),
        SourceReference(Path("unused"), 0, 0),
    )
    data = data.with_rows(data.table.reverse(), data.row_ids.reverse())
    result = prepare_dashboard(
        data, PlotSettings(relationship_features=("b", "a", "constant"))
    )
    grid = result.relationships
    assert grid is not None and grid.names == ("b", "a", "constant")
    np.testing.assert_allclose(grid.values, grid.values.T, equal_nan=True)
    assert grid.values[0, 1] == pytest.approx(-1)
    assert np.isnan(grid.values[2, 2])
    assert sum(grid.diagonals[0].counts) == 200
    points, mirror = grid.cells[0][1], grid.cells[1][0]
    assert points is not None and mirror is not None
    assert points.x_name == "a" and points.y_name == "b"
    np.testing.assert_array_equal(points.x, mirror.y)
    assert points.revision == data.revision and len(points.x) == 150
    for row, position in zip(points.row_ids, points.positions, strict=True):
        assert data.row_ids[int(position)] == row


def test_heatmap_expansion_avoids_grid_and_rejects_invalid() -> None:
    data = Dataset.from_source(
        pl.DataFrame({f"x{i}": range(10) for i in range(20)}),
        SourceReference(Path("unused"), 0, 0),
    )
    names = tuple(f"x{i}" for i in range(16))
    grid = prepare_dashboard(
        data, PlotSettings(relationship_features=names)
    ).relationships
    assert grid is not None and grid.values.shape == (16, 16)
    assert not grid.diagonals and all(
        cell is None for row in grid.cells for cell in row
    )
    with pytest.raises(ValueError):
        prepare_dashboard(data, PlotSettings(relationship_features=("missing",)))


@pytest.mark.parametrize("mode", [1, 2, 3, 4])
def test_selectable_diagonals_keep_independent_ranges_counts_and_identity(
    mode: int,
) -> None:
    data = Dataset.from_source(
        pl.DataFrame(
            {
                "age": [10.0, 20.0, 20.0, None, float("inf")],
                "fare": [100.0, 500.0, 900.0, 300.0, 500.0],
                "constant": [1.0] * 5,
            }
        ),
        SourceReference(Path("unused"), 0, 0),
    )
    grid = prepare_dashboard(
        data,
        PlotSettings(
            relationship_features=("age", "fare", "constant"), diagonal_mode=mode
        ),
    ).relationships
    assert grid is not None and grid.diagonal_mode == mode
    assert len(grid.diagonal_distributions) == 3
    age, fare, constant = grid.diagonal_distributions
    assert age is not None and fare is not None and constant is not None
    assert age.edges[0] == 10 and age.edges[-1] == 20
    assert fare.edges[0] == 100 and fare.edges[-1] == 900
    series = age.series[0]
    assert series.count == 3 and series.sample_count == 3
    assert series.ecdf_x.tolist() == [10, 20] and series.ecdf_y[-1] == 1
    assert np.isfinite(series.kde_y).all()
    assert constant.series[0].box == (1, 1, 1, 1, 1)
    assert not len(constant.series[0].kde_y)
    assert sum(grid.diagonals[0].counts) == 3
    points = grid.cells[0][1]
    assert points is not None and points.row_ids.tolist() == [0, 1, 2]


def test_diagonal_failures_stay_local_and_default_does_not_compute_density() -> None:
    data = Dataset.from_source(
        pl.DataFrame({"large": [1e308, -1e308, 0.0], "id": [1, 2, 3]}),
        SourceReference(Path("unused"), 0, 0),
    )
    default = prepare_dashboard(
        data, PlotSettings(relationship_features=("large", "id"))
    ).relationships
    assert default is not None and not default.diagonal_distributions
    assert default.diagonals[1].counts.sum() == 3  # Explicit numeric ID inspection.
    selected = prepare_dashboard(
        data, PlotSettings(relationship_features=("large", "id"), diagonal_mode=1)
    ).relationships
    assert selected is not None
    assert selected.diagonal_distributions[0] is None
    assert "range" in selected.diagonal_notes[0].lower()
    assert selected.diagonal_distributions[1] is not None
    with pytest.raises(ValueError):
        PlotSettings(diagonal_mode=5).validate()
