from pathlib import Path

import numpy as np
import polars as pl
import pytest

from datelier.dataset import Dataset, SourceReference
from datelier.exploration import PlotSettings, prepare_dashboard


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
