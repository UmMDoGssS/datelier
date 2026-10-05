from collections.abc import Sequence
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset, SourceReference
from datelier.inspection.comparison_settings import (
    ComparisonSettings,
    ComparisonSource,
    Normalization,
)
from datelier.inspection.comparisons.prepare import prepare_comparison, select_bin
from datelier.inspection.comparisons.types import ComparisonInput, PreparedComparison
from datelier.pipeline.operations import Sort, apply_operation
from datelier.plotting.selection import LinkedSelection


def data(
    column: str, values: Sequence[object], dtype: pl.DataType | None = None
) -> Dataset:
    return Dataset.from_source(
        pl.DataFrame({column: pl.Series(list(values), dtype=dtype)}),
        SourceReference(Path(f"{column}.csv"), 0, 0),
    )


def compare(
    a: Dataset, b: Dataset, *, bins: int = 2, top: int = 20, count: bool = False
) -> PreparedComparison:
    sources = (
        ComparisonSource("train", a.table.columns[0], "Train", (0.2, 0.5, 1.0, 1.0)),
        ComparisonSource("test", b.table.columns[0], "Test"),
    )
    settings = ComparisonSettings(
        sources, bins, top, Normalization.COUNT if count else Normalization.DENSITY
    )
    return prepare_comparison(
        (
            ComparisonInput(sources[0], a, "a.csv"),
            ComparisonInput(sources[1], b, "b.csv"),
        ),
        settings,
    )


def test_unequal_sizes_shared_bins_density_counts_and_quality() -> None:
    a = data("x", [0.0, 1.0, 2.0, 3.0, None, float("inf"), float("nan")])
    b = data("other", [0.0, 3.0])
    result = compare(a, b)
    assert result.edges == (0.0, 1.5, 3.0)
    assert [s.counts.tolist() for s in result.series] == [[2, 2], [1, 1]]
    np.testing.assert_allclose(result.series[0].heights, result.series[1].heights)
    for s in result.series:
        assert np.dot(s.heights, np.diff(result.edges)) == pytest.approx(1)
        assert not s.counts.flags.writeable and not s.heights.flags.writeable
    train = result.series[0]
    assert (train.rows, train.included, train.nulls, train.nonfinite) == (7, 4, 1, 2)
    assert train.statistics is not None and train.statistics.mean == 1.5
    assert train.origin.file_id == "train" and train.origin.view == "table"
    assert train.origin.revision == a.revision and train.label == "Train"
    raw = compare(a, b, count=True)
    assert [s.heights.tolist() for s in raw.series] == [[2, 2], [1, 1]]


@pytest.mark.parametrize(
    "values", [[1e308, -1e308], [1e-300, 2e-300], [2.0, 2.0], [1e308, 1e308]]
)
def test_extreme_constant_ranges_have_finite_common_bins(
    values: Sequence[object],
) -> None:
    result = compare(data("a", values), data("b", values[:1]), bins=20)
    assert all(np.diff(result.edges) > 0)
    assert all(np.isfinite(s.heights).all() for s in result.series)
    for s in result.series:
        assert s.counts.sum() == s.included
        assert np.dot(s.heights, np.diff(result.edges)) == pytest.approx(1)


def test_category_order_tail_missing_literals_and_proportions() -> None:
    a = data(
        "label", ["a", "a", "b", None, "Missing (null)", "Other (remaining values)"]
    ).with_role("label", ColumnRole.CATEGORY)
    b = data("group", ["b", "b", "c", None]).with_role("group", ColumnRole.CATEGORY)
    result = compare(a, b, top=2)
    assert result.keys == ("b", "a")
    assert result.labels == ("'b'", "'a'", "Other (remaining values)")
    assert [s.counts.tolist() for s in result.series] == [[1, 2, 3], [2, 0, 2]]
    for s in result.series:
        assert s.heights.sum() == pytest.approx(1)
        assert s.counts.sum() == s.rows
    full = compare(a, b)
    assert "Missing (null)" in full.labels and "'Missing (null)'" in full.labels
    assert "'Other (remaining values)'" in full.labels
    assert result.series[0].mode == "'a'" and result.series[0].mode_count == 2
    selection = select_bin(result, 0, 2, a)
    assert selection.matches == 3 and selection.row_ids == (3, 4, 5)
    assert select_bin(full, 1, full.keys.index(None), b).row_ids == (3,)


def test_empty_source_and_full_category_count_above_previous_sampling_cap() -> None:
    a = data("category", ["x"] * 100_001 + ["y"])
    b = data("other", [], pl.String()).with_role("other", ColumnRole.CATEGORY)
    result = compare(a, b)
    assert result.series[0].counts.sum() == 100_002
    assert result.series[1].heights.sum() == 0
    selected = select_bin(result, 0, result.keys.index("x"), a)
    assert selected.matches == 100_001 and len(selected.row_ids) == 10_000
    empty_numeric = data("other", [], pl.Float64())
    result = compare(data("x", [0.0, 1.0]), empty_numeric)
    assert result.series[1].heights.sum() == 0


def test_sorted_selection_is_bound_to_its_source_and_revision() -> None:
    a = apply_operation(data("x", [3.0, 0.0, 2.0, 1.0]), Sort(("x",)))
    b = data("y", [3.0, 0.0, 2.0, 1.0])
    result = compare(a, b)
    selected = select_bin(result, 0, 0, a)
    assert selected.row_ids == (1, 3) and selected.first_position == 0
    train, test = LinkedSelection(), LinkedSelection()
    train.bind(a.revision)
    test.bind(b.revision)
    assert train.choose(selected.origin.revision, selected.row_ids)
    assert not test.choose(selected.origin.revision, selected.row_ids)
    assert not test.row_ids
    with pytest.raises(ValueError, match="changed"):
        select_bin(result, 0, 0, apply_operation(a, Sort(("x",), descending=True)))


def test_numeric_category_roles_keep_signed_zero_and_nonfinite_quality() -> None:
    a = data("a", [0.0, -0.0, float("nan"), float("inf"), None]).with_role(
        "a", ColumnRole.CATEGORY
    )
    b = data("b", [0.0, 0.0]).with_role("b", ColumnRole.CATEGORY)
    result = compare(a, b)
    assert result.keys[0] == "0.0"
    assert result.series[0].counts[0] == 2
    assert result.series[0].nulls == 1 and result.series[0].nonfinite == 2
    assert result.series[0].counts.sum() == 5
    assert select_bin(result, 0, 0, a).row_ids == (0, 1)


def test_decimal_category_roles_preserve_exact_values_and_missing_counts() -> None:
    a = data(
        "a", [Decimal("1.20"), Decimal("1.20"), None], pl.Decimal(18, 2)
    ).with_role("a", ColumnRole.CATEGORY)
    b = data("b", [Decimal("2.30"), Decimal("2.30")], pl.Decimal(18, 2)).with_role(
        "b", ColumnRole.CATEGORY
    )
    result = compare(a, b)
    assert result.keys == ("1.20", "2.30", None)
    assert [s.counts.tolist() for s in result.series] == [[2, 0, 1], [0, 2, 0]]
    assert all(s.nonfinite == 0 for s in result.series)
    assert select_bin(result, 0, 0, a).row_ids == (0, 1)


@pytest.mark.parametrize("case", ["roles", "family", "column", "finite", "one"])
def test_incompatible_and_missing_columns_are_diagnostic(case: str) -> None:
    a, b = data("a", [1.0, 2.0]), data("b", [1.0, 2.0])
    if case == "roles":
        b = data("b", ["one", "two"])
    elif case == "family":
        a = a.with_role("a", ColumnRole.CATEGORY)
        b = data("b", ["one", "one"])
    elif case == "column":
        b = replace(b, _table=b.table.rename({"b": "missing"}))
    elif case == "finite":
        a, b = data("a", [float("inf")]), data("b", [float("nan")])
    sources = (ComparisonSource("a", "a"), ComparisonSource("b", "b"))
    if case == "one":
        sources = sources[:1]
    with pytest.raises(ValueError):
        prepare_comparison(
            tuple(
                ComparisonInput(s, d, s.file_id)
                for s, d in zip(sources, (a, b), strict=False)
            ),
            ComparisonSettings(sources),
        )
