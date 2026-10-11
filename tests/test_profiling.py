from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from datelier.core.dataset import Dataset, SourceReference
from datelier.inspection.profiles import ProfileKind, prepare_profiles
from datelier.plotting.scatter.prepare import prepare_bars


def dataset(table: pl.DataFrame) -> Dataset:
    return Dataset.from_source(table, SourceReference(Path("unused"), 0, 0))


def test_numeric_temporal_counts_and_quality() -> None:
    data = dataset(
        pl.DataFrame(
            {
                "x": [1.0, 2.0, 3.0, None, float("nan"), float("inf")],
                "day": [date(2024, 1, 1), date(2024, 1, 2)] * 3,
                "label": ["b", "a", "a", "b", "c", None],
            }
        )
    )
    profiles = prepare_profiles(data, bins=2, top=1)
    x, day, label = profiles.columns
    assert profiles.revision == data.revision
    assert (x.minimum, x.maximum, x.mean, x.null_count, x.nonfinite_count) == (
        "1.0",
        "3.0",
        2.0,
        1,
        2,
    )
    assert x.distribution.counts == (2, 1)
    assert sum(day.distribution.counts) == 6
    assert day.minimum == "2024-01-01" and day.kind == ProfileKind.TEMPORAL
    assert label.distribution.labels == ("a",) and label.distribution.counts == (2,)
    assert label.other_count == 3 and label.distinct_count == 3


def test_empty_constant_all_null_and_unsupported() -> None:
    table = pl.DataFrame(
        {
            "constant": [5.0, 5.0],
            "null": [None, None],
            "nested": [[1], [2]],
            "binary": [b"a", b"b"],
        }
    )
    profiles = prepare_profiles(dataset(table))
    assert sum(profiles.columns[0].distribution.counts) == 2
    assert profiles.columns[1].null_count == 2
    assert profiles.columns[2].kind == ProfileKind.NUMERIC
    assert profiles.columns[2].statistics and profiles.columns[2].statistics.mean == 1.5
    assert profiles.columns[3].kind == ProfileKind.UNSUPPORTED
    empty = prepare_profiles(dataset(table.clear()))
    assert all(not p.distribution.counts for p in empty.columns)
    null = prepare_profiles(
        dataset(pl.DataFrame({"x": pl.Series([None], dtype=pl.Float64)}))
    )
    assert null.columns[0].mean is None and "No finite" in null.columns[0].note


def test_high_cardinality_and_wide_limits() -> None:
    table = pl.DataFrame({"count": [str(i) for i in range(100_001)]})
    profile = prepare_profiles(dataset(table), top=3, column="count").columns[0]
    assert profile.kind == ProfileKind.IDENTIFIER and profile.distinct_count == 100_001
    assert not profile.distribution.counts
    # A repeated value makes this categorical; bounded counting still applies.
    table = pl.concat([table, pl.DataFrame({"count": ["0"]})])
    profile = prepare_profiles(dataset(table), top=3).columns[0]
    assert profile.distinct_count == 100_000
    assert len(profile.distribution.labels) == 3
    assert profile.other_count == 99_997 and "sample" in profile.note
    wide = dataset(pl.DataFrame({f"x{i}": [1] for i in range(150)}))
    assert len(prepare_profiles(wide).columns) == 32
    assert len(prepare_profiles(wide, column_limit=128).columns) == 128
    with pytest.raises(ValueError):
        prepare_profiles(wide, column_limit=129)


def test_literal_names_and_boolean_counts() -> None:
    profile = prepare_profiles(
        dataset(pl.DataFrame({"count": [True, False, True], "^x$": [1, 2, 3]}))
    )
    assert profile.columns[0].distribution.counts == (2, 1)
    assert profile.columns[1].mean == 2


def test_extreme_finite_values_keep_counts_and_mean() -> None:
    profile = prepare_profiles(
        dataset(pl.DataFrame({"x": [1e308, -1e308, 0.0]}))
    ).columns[0]
    assert sum(profile.distribution.counts) == 3
    assert profile.mean == 0 and "divided by" in profile.note
    assert profile.histogram_scale == 1e308
    constant = prepare_profiles(dataset(pl.DataFrame({"x": [1e308, 1e308]}))).columns[0]
    assert (
        constant.mean == pytest.approx(1e308) and sum(constant.distribution.counts) == 2
    )


def test_nanosecond_temporal_ranges_and_distributions() -> None:
    for dtype in (pl.Datetime("ns"), pl.Duration("ns"), pl.Time):
        base = 1_704_067_200_000_000_000 if isinstance(dtype, pl.Datetime) else 100
        series = pl.Series("t", [base, base + 1, base + 2], dtype=pl.Int64).cast(dtype)
        profile = prepare_profiles(dataset(series.to_frame()), bins=2).columns[0]
        assert profile.minimum != profile.maximum
        assert profile.distribution.counts == (2, 1)
        assert "relative to the minimum" in profile.note
        assert profile.distribution.tick_labels[0] == profile.minimum
        assert profile.distribution.tick_labels[-1] == profile.maximum
        assert profile.distribution.edges == (0, 1, 2)


@pytest.mark.parametrize(
    "values", [[1.0, 2.0, 3.0], [5.0, 5.0], [1e308, 1e308], [1e16, 1e16 + 2]]
)
def test_value_space_histograms_keep_every_finite_value(values: list[float]) -> None:
    profile = prepare_profiles(dataset(pl.DataFrame({"x": values})), bins=20).columns[0]
    bars = prepare_bars(profile)
    assert len(bars.edges) == len(bars.counts) + 1
    assert np.all(np.isfinite(bars.edges)) and np.all(np.diff(bars.edges) > 0)
    assert bars.edges[0] <= min(values) <= max(values) <= bars.edges[-1]
    assert bars.counts.sum() == len(values)
    assert np.all(bars.positions >= bars.edges[:-1])
    assert not bars.edges.flags.writeable and not bars.counts.flags.writeable


def test_categories_include_other_with_matching_labels() -> None:
    profile = prepare_profiles(
        dataset(pl.DataFrame({"group": ["a", "b", "a", "c", None]})), top=1
    ).columns[0]
    bars = prepare_bars(profile)
    assert bars.labels == ("a", "Other (remaining values)")
    assert bars.counts.tolist() == [2, 2]
    assert bars.counts.sum() + profile.null_count == 5
    assert not len(bars.edges)
