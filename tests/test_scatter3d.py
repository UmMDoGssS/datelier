from pathlib import Path

import numpy as np
import polars as pl
import pytest

from datelier.dataset import Dataset, SourceReference
from datelier.plotting import prepare_scatter
from datelier.projection import projected_nearest, projected_rectangle


def test_three_axis_finite_filter_and_source_positions() -> None:
    data = Dataset.from_source(
        pl.DataFrame(
            {
                "x": [1.0, 2.0, 3.0, 4.0],
                "y": [4.0, 3.0, 2.0, 1.0],
                "z": [0.0, None, 2.0, float("inf")],
            }
        ),
        SourceReference(Path("unused"), 0, 0),
    )
    data = data.with_rows(data.table.reverse(), data.row_ids.reverse())
    points = prepare_scatter(data, "x", "y", z="z")
    assert points.row_ids.tolist() == [2, 0] and points.positions.tolist() == [1, 3]
    assert points.z is not None and points.z.tolist() == [2, 0]
    assert not points.z.flags.writeable and points.eligible_rows == 2
    with pytest.raises(ValueError):
        prepare_scatter(data, "x", "y", z="x")


def test_projected_picking_depth_ties_brush_and_nonfinite() -> None:
    pixels = np.array([[10.0, 20.0], [10.0, 20.0], [20.0, 30.0], [np.nan, 0.0]])
    depths = np.array([3.0, 1.0, 2.0, 0.0])
    assert projected_nearest(pixels, depths, (10, 20)) == 1
    assert projected_nearest(pixels, depths, (100, 200)) is None
    assert projected_nearest(pixels, depths, (np.nan, 0)) is None
    assert projected_rectangle(pixels, (9, 19), (11, 21)).tolist() == [
        True,
        True,
        False,
        False,
    ]
