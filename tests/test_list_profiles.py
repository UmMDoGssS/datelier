import math
from pathlib import Path

import polars as pl
import pytest

from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset, SourceReference
from datelier.inspection.lists import flatten_elements, prepare_list
from datelier.inspection.profile_preview import ProfileRequest, prepare_profile_group
from datelier.inspection.profile_selection import ProfileSelection
from datelier.inspection.profiles import ProfileKind, prepare_profiles
from datelier.pipeline.history import Pipeline
from datelier.pipeline.operations import Sort
from datelier.plotting.distributions import DistributionSettings


def data(series: pl.Series) -> Dataset:
    return Dataset.from_source(series.to_frame(), SourceReference(Path("unused"), 0, 0))


def test_list_numeric_statistics_use_all_leaves_and_keep_container_nulls_separate() -> (
    None
):
    series = pl.Series("xs", [[1.0, None, math.nan], None, [], [3.0, math.inf, 5.0]])
    dataset = data(series)
    assert dataset.role("xs").role == ColumnRole.LIST_NUMERIC
    profile = prepare_profiles(dataset).columns[0]
    assert profile.kind == ProfileKind.NUMERIC and profile.dtype == str(series.dtype)
    assert profile.statistics is not None
    stats = profile.statistics
    assert (stats.mean, stats.minimum, stats.maximum, stats.median) == pytest.approx(
        (3, 1, 5, 3)
    )
    assert (stats.nonnull, stats.nulls, stats.nans, stats.nonfinites, stats.finite) == (
        5,
        1,
        1,
        2,
        3,
    )
    assert (profile.nonnull_count, profile.null_count, profile.unique_count) == (
        5,
        1,
        5,
    )
    assert sum(profile.distribution.counts) == 3
    assert profile.list_statistics is not None
    lists = profile.list_statistics
    assert (lists.elements, lists.null_elements) == (6, 1)
    outer = lists.dimensions[0]
    assert (
        outer.containers,
        outer.nulls,
        outer.empty,
        outer.mean,
        outer.minimum,
        outer.maximum,
    ) == (4, 1, 1, 2, 0, 3)
    assert series.equals(dataset.table["xs"]) and dataset.row_ids.to_list() == [
        0,
        1,
        2,
        3,
    ]


def test_nested_lengths_and_shapes_distinguish_ragged_unknown_and_empty() -> None:
    series = pl.Series("xs", [[[1, 2], [3, 4]], [[1], [2, 3]], [], None, [None, [5]]])
    leaves, stats = prepare_list(series)
    assert leaves.to_list() == [1, 2, 3, 4, 1, 2, 3, 5]
    assert flatten_elements(series).equals(leaves)
    assert (stats.rectangular, stats.ragged, stats.unknown) == (1, 1, 2)
    assert dict(stats.shapes) == {"2 × 2": 1, "ragged": 1, "0 × ?": 1, "unknown": 1}
    outer, inner = stats.dimensions
    assert (outer.depth, outer.containers, outer.nulls, outer.empty, outer.mean) == (
        1,
        5,
        1,
        1,
        1.5,
    )
    assert (inner.depth, inner.containers, inner.nulls, inner.empty, inner.mean) == (
        2,
        6,
        1,
        0,
        1.6,
    )
    three = pl.from_dicts([{"xs": [[[]]]}, {"xs": [[[1, 2], [3, 4]]]}])["xs"]
    _, shapes = prepare_list(three)
    assert dict(shapes.shapes) == {"1 × 1 × 0": 1, "1 × 2 × 2": 1}
    assert shapes.rectangular == 2 and len(shapes.dimensions) == 3


@pytest.mark.parametrize(
    "series",
    [
        pl.Series("xs", [[], None], dtype=pl.List(pl.Int64)),
        pl.Series("xs", [None, None], dtype=pl.List(pl.List(pl.Float64))),
        pl.Series("xs", [], dtype=pl.List(pl.String)),
        pl.Series("xs", [None, [None]], dtype=pl.List(pl.Null)),
        pl.Series("xs", [[{"a": 1}], []]),
        pl.Series("xs", [[[1, 2], [3, 4]], None], dtype=pl.Array(pl.Int64, (2, 2))),
    ],
)
def test_empty_null_object_and_array_lists_remain_profileable(
    series: pl.Series,
) -> None:
    dataset = data(series)
    request = ProfileRequest(DistributionSettings(("xs",)))
    group = prepare_profile_group(dataset, request)
    profile = group.profiles.columns[0]
    assert profile.list_statistics is not None
    leaves, stats = prepare_list(series)
    assert stats == profile.list_statistics
    assert stats.elements == len(leaves)
    assert profile.null_count == leaves.null_count()
    assert dataset.table["xs"].equals(series)


def test_strings_booleans_and_counts_cap_use_leaf_population(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import datelier.inspection.profiles as profiles

    monkeypatch.setattr(profiles, "COUNT_ROW_LIMIT", 3)
    dataset = data(pl.Series("words", [["a", "b", "a", "c"], [], None, [None, "b"]]))
    profile = prepare_profiles(dataset, column="words").columns[0]
    assert profile.kind == ProfileKind.CATEGORICAL
    assert profile.distribution.labels == ("a", "b")
    assert profile.distribution.counts == (2, 1)
    assert (profile.nonnull_count, profile.null_count, profile.unique_count) == (
        5,
        1,
        3,
    )
    assert "first 3 elements" in profile.note
    boolean = prepare_profiles(
        data(pl.Series("flags", [[True, False], [True], None]))
    ).columns[0]
    assert boolean.distribution.labels == ("True", "False")
    assert boolean.distribution.counts == (2, 1)


def test_shape_counts_are_bounded_but_account_for_every_nonnull_record() -> None:
    _, stats = prepare_list(
        pl.Series("xs", [list(range(i)) for i in range(25)] + [None])
    )
    assert len(stats.shapes) == 12
    assert sum(count for _, count in stats.shapes) + stats.other_shapes == 25
    assert stats.rectangular == 25 and stats.other_shapes == 13


def test_list_numeric_charts_and_selection_remain_stable_across_sorting() -> None:
    dataset = data(
        pl.Series("xs", [list(range(i * 200, (i + 1) * 200)) for i in range(20)])
    )
    selection = ProfileSelection()
    selection.bind(dataset)
    assert selection.columns == ("xs",) and selection.text_column() is None
    request = ProfileRequest(DistributionSettings(("xs",), density=False, seed=7))
    original = prepare_profile_group(dataset, request)
    sorted_data = Pipeline.start(dataset).apply(Sort(("xs",), True)).current
    reordered = prepare_profile_group(sorted_data, request)
    assert original.comparison is not None and reordered.comparison is not None
    a, b = original.comparison.series[0], reordered.comparison.series[0]
    assert a.count == 4000 and a.sample_count == 2000
    assert a.histogram.sum() == 4000
    assert (a.ecdf_x == b.ecdf_x).all() and (a.ecdf_y == b.ecdf_y).all()
    assert (
        a.box == b.box
        and original.profiles.columns[0].statistics
        == reordered.profiles.columns[0].statistics
    )
    assert sorted_data.row_ids.to_list() != dataset.row_ids.to_list()


def test_objects_are_available_for_profile_quality_and_complete_inspect() -> None:
    dataset = data(pl.Series("obj", [{"a": 1}, None, {}]))
    assert dataset.role("obj").role == ColumnRole.OBJECT
    selection = ProfileSelection()
    selection.bind(dataset)
    assert selection.columns == ("obj",)
    profile = prepare_profile_group(
        dataset, ProfileRequest(DistributionSettings(("obj",)))
    ).profiles.columns[0]
    assert profile.kind == ProfileKind.OBJECT
    assert (profile.nonnull_count, profile.null_count) == (2, 1)
    assert "Inspect" in profile.note
