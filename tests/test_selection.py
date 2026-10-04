from pathlib import Path

import numpy as np
import polars as pl
import pytest

from datelier.dataset import Dataset, SourceReference
from datelier.exploration import prepare_dashboard
from datelier.gui_plot_controls import PlotControls
from datelier.operations import Comparison, Filter, SelectColumns, Sort
from datelier.pipeline import Pipeline
from datelier.plotting import prepare_scatter
from datelier.selection import LinkedSelection


def data() -> Dataset:
    return Dataset.from_source(
        pl.DataFrame({"x": range(20), "y": range(20)}),
        SourceReference(Path("unused"), 0, 0),
    )


def test_point_brush_table_overlay_after_sort_filter_and_sample() -> None:
    source = data()
    active = (
        Pipeline.start(source)
        .apply(Sort(("x",), descending=True))
        .apply(Filter("x", Comparison.GE, 5))
        .current
    )
    points = prepare_scatter(active, "x", "y", limit=4)
    assert points.positions.tolist() == [0, 4, 9, 14]
    selected = LinkedSelection()
    selected.bind(active.revision)
    # Plot click on the sampled coordinate reveals its current table position.
    assert selected.nearest(points, 10, 10, 10, 10) == 9
    assert selected.row_ids == {10}
    xs, ys = selected.overlay(points)
    np.testing.assert_array_equal(xs, [10])
    np.testing.assert_array_equal(ys, [10])
    assert selected.rectangle(points, 16, 16, 9, 9)
    assert selected.row_ids == {15, 10}
    # Table selection of an unsampled row is retained; only visible points highlight.
    selected.choose(active.revision, [6])
    assert not len(selected.overlay(points)[0])
    selected.choose(active.revision, [19], toggle=True)
    assert selected.row_ids == {6, 19}
    assert selected.overlay(points)[0].tolist() == [19]
    assert selected.nearest(points, -100, -100, 10, 10) is None


def test_stale_selection_and_revision_reset() -> None:
    source = data()
    points = prepare_scatter(source, "x", "y")
    selected = LinkedSelection()
    selected.bind(source.revision)
    selected.choose(source.revision, [2])
    selected.bind(source.revision)
    assert selected.row_ids == {2}
    next_revision = (
        Pipeline.start(source).apply(Filter("x", Comparison.GT, 3)).current.revision
    )
    selected.bind(next_revision)
    assert not selected.row_ids
    assert not selected.rectangle(points, 0, 0, 10, 10)
    assert selected.nearest(points, 2, 2, 10, 10) is None
    assert not selected.choose(source.revision, [2])
    assert not len(selected.overlay(points)[0])
    with pytest.raises(ValueError):
        selected.choose(next_revision, range(10_001))
    assert not selected.row_ids


def test_settings_focus_any_column_and_rebind_after_removed_columns() -> None:
    source = Dataset.from_source(
        pl.DataFrame({f"x{i}": range(5) for i in range(140)}),
        SourceReference(Path("unused"), 0, 0),
    )
    controls = PlotControls()
    controls.bind(source)
    controls.profile_index = 140
    controls.custom_scatter = True
    controls.x_index, controls.y_index = 138, 139
    controls.point_limit = 3
    dashboard = prepare_dashboard(source, controls.settings())
    assert [p.name for p in dashboard.profiles.columns] == ["x139"]
    assert dashboard.scatters[0].x_name == "x138"
    assert len(dashboard.scatters[0].x) == 3
    transformed = Pipeline.start(source).apply(SelectColumns(("x0",))).current
    controls.bind(transformed)
    assert not controls.custom_scatter and controls.profile_index == 0
    assert not prepare_dashboard(transformed, controls.settings()).scatters
    # Empty/one numeric schemas can be rebound again without invalid indices.
    controls.bind(source)
    assert controls.numeric == tuple(source.table.columns)
