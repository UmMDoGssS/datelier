from pathlib import Path

import numpy as np
import polars as pl

from datelier.analysis.cluster_colors import prepare_cluster_colors
from datelier.analysis.input import prepare_input
from datelier.analysis.parameters import DBSCANParameters
from datelier.analysis.runner import run_analysis
from datelier.analysis.types import AnalysisRequest, ClusteringResult
from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset, SourceReference
from datelier.plotting.colors import (
    NEUTRAL,
    PointColors,
    continuous_colors,
    prepare_colors,
)
from datelier.plotting.data import prepare_scatter
from datelier.plotting.selection import LinkedSelection


def data(table: pl.DataFrame) -> Dataset:
    return Dataset.from_source(table, SourceReference(Path("unused"), 0, 0))


def assert_partition(colors: PointColors) -> None:
    indices = np.concatenate([s.indices for s in colors.series])
    np.testing.assert_array_equal(np.sort(indices), np.arange(len(colors.rgba)))
    assert not colors.rgba.flags.writeable
    for series in colors.series:
        assert not series.indices.flags.writeable
        if not series.continuous:
            assert np.all(colors.rgba[series.indices] == series.rgba)


def test_category_entries_partition_displayed_rows_after_sorting_and_sampling() -> None:
    dataset = data(
        pl.DataFrame(
            {
                "x": range(60),
                "y": [float(i % 7) for i in range(60)],
                "group": [None if i % 15 == 0 else str(i % 14) for i in range(60)],
            }
        )
    )
    reverse = dataset.with_rows(dataset.table.reverse(), dataset.row_ids.reverse())
    points = prepare_scatter(reverse, "x", "y", limit=40, color="group")
    assert points.colors is not None and points.colors.scale is None
    assert_partition(points.colors)
    assert {s.label for s in points.colors.series} >= {"Other", "Missing"}
    for series in points.colors.series:
        if series.label not in ("Other", "Missing"):
            for index in series.indices:
                row_id = int(points.row_ids[index])
                assert dataset.table["group"][row_id] == series.label


def test_categorical_numeric_override_changes_the_native_legend_model() -> None:
    dataset = data(pl.DataFrame({"value": [1, 2, 1, 2]}))
    positions = np.arange(4, dtype=np.uint64)
    continuous = prepare_colors(dataset, positions, "value")
    assert continuous.scale is not None
    categorical = prepare_colors(
        dataset.with_role("value", ColumnRole.CATEGORY), positions, "value"
    )
    assert categorical.scale is None
    assert {s.label for s in categorical.series} == {"1", "2"}
    assert_partition(categorical)


def test_continuous_scales_missing_constants_and_extremes_are_truthful() -> None:
    values = np.array([1, 5, np.nan, np.inf], dtype=float)
    colors = continuous_colors(values, "measurement")
    assert colors.scale is not None and (
        colors.scale.minimum,
        colors.scale.maximum,
    ) == (1, 5)
    assert_partition(colors)
    assert colors.series[0].continuous and colors.series[1].rgba == NEUTRAL
    constant = continuous_colors(np.array([5, 5, np.nan]), "fixed")
    assert constant.scale is None and constant.series[0].label == "fixed: 5"
    assert_partition(constant)
    extreme = continuous_colors(np.array([-1e308, 1e308]), "extreme")
    assert extreme.scale is not None
    assert (extreme.scale.minimum, extreme.scale.maximum, extreme.scale.divisor) == (
        -1,
        1,
        1e308,
    )
    assert_partition(extreme)
    empty = continuous_colors(np.array([], dtype=float), "empty")
    assert empty.scale is None and not empty.series
    missing = continuous_colors(np.array([np.nan, np.inf]), "missing")
    assert missing.scale is None
    assert_partition(missing)


def test_noise_and_unassigned_colors_have_native_series() -> None:
    dataset = data(
        pl.DataFrame({"x": [0.0, 10.0, 20.0, None], "y": [0.0, 10.0, 20.0, 5.0]})
    )
    request = AnalysisRequest(
        ("x", "y"), DBSCANParameters(epsilon=0.01, min_samples=3), row_limit=100
    )
    result = run_analysis(prepare_input(dataset, request))
    assert isinstance(result, ClusteringResult)
    colors = prepare_cluster_colors(dataset, np.arange(4, dtype=np.uint64), result)
    assert {s.label for s in colors.series} == {
        "Noise (fit 3)",
        "Unassigned / excluded",
    }
    assert_partition(colors)


def test_hidden_series_are_excluded_from_brushing_without_losing_row_identity() -> None:
    dataset = data(pl.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [1.0, 2.0, 3.0, 4.0]}))
    reverse = dataset.with_rows(dataset.table.reverse(), dataset.row_ids.reverse())
    points = prepare_scatter(reverse, "x", "y")
    selection = LinkedSelection()
    selection.bind(points.revision)
    selection.rectangle(
        points, 0, 0, 5, 5, visible=np.array([True, False, True, False])
    )
    assert selection.row_ids == {3, 1}
    selection.rectangle(points, 0, 0, 5, 5, visible=np.zeros(4, dtype=bool))
    assert not selection.row_ids
