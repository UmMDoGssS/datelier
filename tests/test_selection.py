from pathlib import Path

import numpy as np
import polars as pl
import pytest

from datelier.application.exploration import PlotState
from datelier.core.dataset import Dataset, SourceReference
from datelier.inspection.exploration import prepare_dashboard
from datelier.pipeline.history import Pipeline
from datelier.pipeline.operations import Comparison, Filter, SelectColumns, Sort
from datelier.plotting.scatter import LinkedSelection, prepare_scatter


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
    assert selected.unselected(points)[0].tolist() == [15, 10, 5]
    assert len(selected.overlay(points)[0]) + len(
        selected.unselected(points)[0]
    ) == len(points.x)
    assert selected.nearest(points, -100, -100, 10, 10) is None
    assert selected.nearest(points, float("nan"), 10, 10, 10) is None
    assert selected.nearest(points, 10, 10, 0, 10) is None


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


def test_linked_highlights_across_alternating_sampled_views() -> None:
    source = data()
    first = prepare_scatter(source, "x", "y", limit=4)
    second = prepare_scatter(source, "y", "x", limit=20)
    selected = LinkedSelection()
    selected.bind(source.revision)
    selected.choose(source.revision, [6, 19])
    for _ in range(3):
        assert selected.overlay(first)[0].tolist() == [6, 19]
        assert selected.overlay(second)[0].tolist() == [6, 19]
        assert len(selected.unselected(first)[0]) == 2
    selected.choose(source.revision, [2])
    assert not len(selected.overlay(first)[0])
    assert selected.overlay(second)[0].tolist() == [2]
    selected.bind(data().revision)
    assert not len(selected.overlay(first)[0])
    assert not len(selected.overlay(second)[0])


def test_settings_focus_any_column_and_rebind_after_removed_columns() -> None:
    source = Dataset.from_source(
        pl.DataFrame({f"x{i}": [float(v) for v in range(5)] for i in range(140)}),
        SourceReference(Path("unused"), 0, 0),
    )
    controls = PlotState()
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


def test_selection_mask_is_revision_bound_and_read_only() -> None:
    source = data()
    points = prepare_scatter(source, "x", "y", limit=4)
    selection = LinkedSelection()
    selection.bind(source.revision)
    selection.choose(source.revision, [6, 19])
    mask = selection.mask(points)
    assert points.row_ids[mask].tolist() == [6, 19]
    with pytest.raises(ValueError):
        mask[0] = False
    selection.choose(source.revision, [2])
    assert not selection.mask(points).any()
    selection.choose(source.revision, [19])
    assert points.row_ids[selection.mask(points)].tolist() == [19]
    selection.bind(data().revision)
    assert not selection.mask(points).any()
