import math
from pathlib import Path

import polars as pl
import pytest

from datelier.core.dataset import Dataset, SourceReference
from datelier.profile_statistics import prepare_numeric_statistics
from datelier.profiling import prepare_profiles


def test_finite_statistics_and_separate_quality_counts() -> None:
    values = pl.Series("x", [1.0, 2.0, 3.0, 4.0, None, math.nan, math.inf, -math.inf])
    stats = prepare_numeric_statistics(values)
    assert (
        stats.nonnull,
        stats.uniques,
        stats.finite,
        stats.nulls,
        stats.nans,
        stats.nonfinites,
    ) == (7, 7, 4, 1, 1, 3)
    assert stats.mean == 2.5 and stats.std == pytest.approx(math.sqrt(5 / 3))
    assert (stats.minimum, stats.q25, stats.median, stats.q75, stats.maximum) == (
        1,
        1.75,
        2.5,
        3.25,
        4,
    )
    assert (stats.mode, stats.mode_count, stats.mode_ties) == (1, 1, 4)


def test_mode_rounding_ties_and_exact_integers() -> None:
    stats = prepare_numeric_statistics(pl.Series([1.231, 1.234, 2.001, 2.004]))
    assert (stats.mode, stats.mode_count, stats.mode_ties) == (1.23, 2, 2)
    assert stats.rounded_mode
    integer = prepare_numeric_statistics(pl.Series([2**53 + 1, 2**53 + 1, 2**53 + 2]))
    assert integer.minimum == integer.mode == 2**53 + 1
    assert integer.maximum == 2**53 + 2 and not integer.rounded_mode


def test_empty_singleton_constant_and_extreme_values() -> None:
    empty = prepare_numeric_statistics(pl.Series([None, math.nan, math.inf]))
    assert empty.mean is empty.std is empty.mode is empty.minimum is None
    assert (empty.nulls, empty.nans, empty.nonfinites) == (1, 1, 2)
    single = prepare_numeric_statistics(pl.Series([3.0]))
    assert single.mean == single.median == 3 and single.std is None
    constant = prepare_numeric_statistics(pl.Series([1e308, 1e308]))
    assert constant.std == 0 and constant.mode == 1e308
    extreme = prepare_numeric_statistics(pl.Series([-1e308, 0.0, 1e308]))
    assert extreme.mean == extreme.median == 0
    assert extreme.std == pytest.approx(1e308)
    assert extreme.q25 == pytest.approx(-5e307) and extreme.q75 == pytest.approx(5e307)
    overflow = prepare_numeric_statistics(pl.Series([-1.7e308, 1.7e308]))
    assert overflow.std is None and overflow.mean == 0


def test_profiles_attach_original_unit_statistics_and_exact_category_counts() -> None:
    data = Dataset.from_source(
        pl.DataFrame({"x": [1.0, 2.0, None], "cat": ["a", "a", None]}),
        SourceReference(Path("unused"), 0, 0),
    )
    numeric, category = prepare_profiles(data).columns
    assert numeric.statistics is not None and numeric.statistics.mean == 1.5
    assert (category.nonnull_count, category.unique_count, category.null_count) == (
        2,
        1,
        1,
    )
    assert category.statistics is None
