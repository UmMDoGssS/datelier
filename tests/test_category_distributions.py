from pathlib import Path

import numpy as np
import polars as pl
import pytest

from datelier.core.dataset import Dataset, SourceReference
from datelier.pipeline.operations import Sort, apply_operation
from datelier.plotting.categories import CategoryRepresentation as Mode
from datelier.plotting.categories import CategorySettings, prepare_category_chart
from datelier.workspace.codec import decode_record, encode


def data(table: pl.DataFrame) -> Dataset:
    return Dataset.from_source(table, SourceReference(Path("unused"), 0, 0))


@pytest.mark.parametrize("mode", [Mode.BOX, Mode.VIOLIN])
def test_grouped_quartiles_missing_categories_and_nonfinite_exclusion(
    mode: Mode,
) -> None:
    dataset = data(
        pl.DataFrame(
            {
                "group": ["a"] * 5 + ["b"] * 2 + [None, "a", "b"],
                "value": [
                    0.0,
                    1.0,
                    1.0,
                    2.0,
                    100.0,
                    5.0,
                    5.0,
                    -2.0,
                    None,
                    float("inf"),
                ],
            }
        )
    )
    result = prepare_category_chart(
        dataset, CategorySettings("group", mode, value="value")
    )
    assert result.revision == dataset.revision
    assert (result.included_rows, result.excluded_values) == (8, 2)
    assert result.labels == ("a", "b", "Missing (null)")
    a, b, missing = result.distributions
    assert a.box == (0, 1, 1, 2, 2) and a.outliers.tolist() == [100]
    assert b.box == (5, 5, 5, 5, 5) and not len(b.kde_y)
    assert missing.box == (-2, -2, -2, -2, -2)
    assert result.counts.tolist() == [[5, 2, 1]]
    assert result.value_label == "value"
    assert result.row_ids[0] == ((0, 1, 2, 3, 4), (5, 6), (7,))
    assert not a.kde_y.flags.writeable and not result.counts.flags.writeable


def test_other_bucket_keeps_distribution_rows_and_sorted_source_links() -> None:
    dataset = data(
        pl.DataFrame(
            {"cat": ["a", "a", "b", "c", "d"], "value": [5.0, 1.0, 3.0, 2.0, 4.0]}
        )
    )
    sorted_data = apply_operation(dataset, Sort(("value",)))
    settings = CategorySettings("cat", Mode.BOX, value="value", top=1)
    first = prepare_category_chart(dataset, settings)
    second = prepare_category_chart(sorted_data, settings)
    assert second.labels == ("a", "Other (remaining values)")
    assert second.other_categories == 3 and second.counts.sum() == 5
    assert set(second.row_ids[0][1]) == {2, 3, 4}
    for i, position in enumerate(second.first_positions[0]):
        assert sorted_data.row_ids[position] in second.row_ids[0][i]
    for a, b in zip(first.distributions, second.distributions, strict=True):
        assert a.box == b.box
        np.testing.assert_array_equal(a.ecdf_x, b.ecdf_x)


def test_density_cohort_is_seeded_bounded_and_order_independent() -> None:
    dataset = data(pl.DataFrame({"cat": ["a"] * 2500, "value": range(2500)}))
    settings = CategorySettings(
        "cat", Mode.VIOLIN, value="value", bandwidth=0.5, seed=17
    )
    first = prepare_category_chart(dataset, settings).distributions[0]
    reverse = dataset.with_rows(dataset.table.reverse(), dataset.row_ids.reverse())
    second = prepare_category_chart(reverse, settings).distributions[0]
    assert first.count == 2500 and first.sample_count == 2000
    np.testing.assert_array_equal(first.ecdf_x, second.ecdf_x)
    np.testing.assert_array_equal(first.kde_y, second.kde_y)
    assert first.box == second.box
    assert decode_record(CategorySettings, encode(settings)) == settings


def test_empty_extreme_and_close_measurements_are_explicit() -> None:
    dataset = data(
        pl.DataFrame({"cat": ["a", "a", "a"], "value": [-1e308, 0.0, 1e308]})
    )
    settings = CategorySettings("cat", Mode.BOX, value="value")
    result = prepare_category_chart(dataset, settings)
    assert result.distribution_scale == 1e308 and "/ 1e+308" in result.value_label
    assert result.distributions[0].box == pytest.approx((-1, -0.5, 0, 0.5, 1))
    assert np.isfinite(result.values).all()
    close = data(pl.DataFrame({"cat": ["a", "a"], "value": [1e16, 1e16 + 2]}))
    assert prepare_category_chart(close, settings).distributions[0].box is not None
    empty = data(pl.DataFrame({"cat": ["a", "a"], "value": [None, float("inf")]}))
    chart = prepare_category_chart(empty, settings)
    assert not chart.labels and not chart.distributions and chart.excluded_values == 2


def test_group_sampling_and_linked_selection_limits() -> None:
    dataset = data(pl.DataFrame({"cat": ["a"] * 100_010, "value": range(100_010)}))
    chart = prepare_category_chart(
        dataset, CategorySettings("cat", Mode.BOX, value="value")
    )
    assert chart.input_rows == chart.included_rows == 100_000
    assert chart.total_rows == 100_010
    assert chart.distributions[0].count == 100_000
    assert len(chart.row_ids[0][0]) == 10_000
