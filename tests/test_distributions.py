from pathlib import Path

import numpy as np
import polars as pl
import pytest

from datelier.core.dataset import Dataset, SourceReference
from datelier.plotting.distributions import DistributionSettings, prepare_comparison


def data(table: pl.DataFrame) -> Dataset:
    return Dataset.from_source(table, SourceReference(Path("unused"), 0, 0))


def test_shared_bins_density_ecdf_and_box() -> None:
    dataset = data(
        pl.DataFrame(
            {
                "x": [0.0, 1.0, 1.0, 2.0, 100.0, None],
                "y": [1.0, 2.0, 3.0, 4.0, 5.0, float("inf")],
            }
        )
    )
    result = prepare_comparison(dataset, DistributionSettings(("x", "y")), bins=4)
    x, y = result.series
    for series in (x, y):
        assert np.dot(series.histogram, np.diff(result.edges)) == pytest.approx(1)
        assert np.all(np.diff(series.ecdf_y) > 0)
        assert series.ecdf_y[-1] == 1
    assert x.ecdf_x.tolist() == [0, 1, 2, 100]
    assert x.ecdf_y.tolist() == [0.2, 0.6, 0.8, 1.0]
    assert x.box == (0, 1, 1, 2, 2)
    assert x.outliers.tolist() == [100]
    assert np.all(np.isfinite(y.kde_y))


def test_empty_constant_scaling_and_bandwidth() -> None:
    dataset = data(
        pl.DataFrame(
            {"x": [1.0, 2.0, 3.0], "c": [5.0, 5.0, 5.0], "empty": [None] * 3},
            schema_overrides={"empty": pl.Float64},
        )
    )
    settings = DistributionSettings(("x", "c", "empty"), standardize=True)
    result = prepare_comparison(dataset, settings)
    x, c, empty = result.series
    assert np.mean(x.ecdf_x) == pytest.approx(0, abs=1e-15)
    assert c.ecdf_x.tolist() == [0]
    assert not len(c.kde_y) and empty.box is None
    narrow = prepare_comparison(dataset, DistributionSettings(("x",), bandwidth=0.5))
    wide = prepare_comparison(dataset, DistributionSettings(("x",), bandwidth=2))
    assert not np.allclose(narrow.series[0].kde_y, wide.series[0].kde_y)


def test_seeded_sample_invariant_to_display_order_and_bounded() -> None:
    dataset = data(pl.DataFrame({"x": range(3000)}))
    settings = DistributionSettings(("x",))
    first = prepare_comparison(dataset, settings).series[0]
    reversed_data = dataset.with_rows(
        dataset.table.reverse(), dataset.row_ids.reverse()
    )
    second = prepare_comparison(reversed_data, settings).series[0]
    assert first.sample_count == 2000 and first.count == 3000
    np.testing.assert_array_equal(first.ecdf_x, second.ecdf_x)
    assert not first.ecdf_x.flags.writeable


def test_invalid_and_extreme_comparisons() -> None:
    dataset = data(pl.DataFrame({"x": [-1e308, 1e308], "s": ["a", "b"]}))
    with pytest.raises(ValueError, match="overflows"):
        prepare_comparison(dataset, DistributionSettings(("x",)))
    assert len(prepare_comparison(dataset, DistributionSettings(("x",), True)).series)
    with pytest.raises(ValueError):
        prepare_comparison(dataset, DistributionSettings(("s",)))
    with pytest.raises(ValueError):
        DistributionSettings(("x", "x")).validate()
