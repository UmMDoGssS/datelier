from datetime import date
from pathlib import Path

import polars as pl
import pytest

from datelier.dataset import Dataset, SourceReference
from datelier.profiling import ProfileKind, prepare_profiles


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
        {"constant": [5.0, 5.0], "null": [None, None], "nested": [[1], [2]]}
    )
    profiles = prepare_profiles(dataset(table))
    assert sum(profiles.columns[0].distribution.counts) == 2
    assert profiles.columns[1].null_count == 2
    assert profiles.columns[2].kind == ProfileKind.UNSUPPORTED
    empty = prepare_profiles(dataset(table.clear()))
    assert all(not p.distribution.counts for p in empty.columns)
    null = prepare_profiles(
        dataset(pl.DataFrame({"x": pl.Series([None], dtype=pl.Float64)}))
    )
    assert null.columns[0].mean is None and "No finite" in null.columns[0].note


def test_high_cardinality_and_wide_limits() -> None:
    table = pl.DataFrame({"count": [str(i) for i in range(100_001)]})
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
