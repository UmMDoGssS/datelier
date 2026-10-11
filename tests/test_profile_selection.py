from pathlib import Path

import polars as pl
import pytest

from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset, SourceReference
from datelier.inspection.profiles import ProfileSelection
from datelier.inspection.profiles.preview import ProfileRequest, prepare_profile_group
from datelier.plotting.distributions import DistributionSettings
from datelier.workspace.recipes.codec import decode_record, encode
from datelier.workspace.single import WorkspaceViews


def data() -> Dataset:
    return Dataset.from_source(
        pl.DataFrame(
            {
                "a": [1.0, 2.0, 3.0],
                "b": [10.0, 20.0, 30.0],
                "cat": ["x", "x", "y"],
                "text": ["a", "b", "c"],
                "row_id": [1, 2, 3],
            }
        ),
        SourceReference(Path("unused"), 0, 0),
    )


def test_exclusive_category_numeric_group_and_intentional_empty_selection() -> None:
    selection = ProfileSelection()
    selection.bind(data(), "b")
    assert selection.columns == ("b",)
    selection.toggle("a")
    assert selection.columns == ("a", "b")
    selection.toggle("cat")
    assert selection.columns == ("cat",)
    selection.toggle("b")
    assert selection.columns == ("b",)
    selection.toggle("b")
    selection.bind(data())
    assert selection.columns == ()
    selection.select_numeric()
    assert selection.columns == ("a", "b")
    assert {c.name for c in selection.choices} == {"a", "b", "cat", "text"}


def test_text_is_exclusive_and_string_categories_keep_their_interpretation() -> None:
    dataset = data()
    selection = ProfileSelection(("a", "b"))
    selection.bind(dataset)
    selection.toggle("text")
    assert selection.columns == ("text",)
    assert selection.text_column() == "text"
    selection.toggle("cat")
    assert selection.text_column() is None
    assert selection.text_column(prefer_text=True) == "cat"
    assert dataset.role("cat").role == ColumnRole.CATEGORY
    selection.toggle("a")
    assert selection.columns == ("a",)
    assert selection.text_column(prefer_text=True) is None
    selection.select_numeric()
    assert selection.columns == ("a", "b")


def test_every_string_field_remains_accessible_and_removed_text_is_pruned() -> None:
    dataset = data()
    for role in (
        ColumnRole.EXTERNAL_TEXT,
        ColumnRole.PATH,
        ColumnRole.IDENTIFIER,
        ColumnRole.IMAGE,
        ColumnRole.AUDIO,
    ):
        selection = ProfileSelection(("text",))
        selection.bind(dataset.with_role("text", role))
        assert selection.text_column() == (None if role == ColumnRole.IMAGE else "text")
        assert selection.text_column(prefer_text=True) == "text"
        selection.bind(dataset.with_rows(dataset.table.drop("text"), dataset.row_ids))
        assert selection.columns == ()
        assert selection.text_column() is None


def test_selection_follows_names_and_role_changes() -> None:
    selection = ProfileSelection(("b", "a", "missing", "row_id"))
    dataset = data()
    selection.bind(
        dataset.with_rows(
            dataset.table.select("cat", "b", "a", "text", "row_id"), dataset.row_ids
        )
    )
    assert selection.columns == ("b", "a")
    selection.bind(dataset.with_role("b", ColumnRole.CATEGORY))
    assert selection.columns == ("b",)
    selection.bind(dataset.with_role("b", ColumnRole.IDENTIFIER))
    assert selection.columns == ()


def test_unlimited_explicit_profiles_and_comparisons_bypass_automatic_limits() -> None:
    table = pl.DataFrame({f"n{i}": [i, i, None] for i in range(140)})
    dataset = Dataset.from_source(table, SourceReference(Path("unused"), 0, 0))
    result = prepare_profile_group(
        dataset, ProfileRequest(DistributionSettings(tuple(table.columns)))
    )
    assert len(result.profiles.columns) == 140
    assert result.comparison is not None and len(result.comparison.series) == 140
    assert all(
        p.statistics and p.statistics.finite == 2 and p.statistics.nulls == 1
        for p in result.profiles.columns
    )
    assert all(s.count == 2 and s.sample_count == 2 for s in result.comparison.series)


def test_scaled_comparisons_keep_statistics_in_original_units_and_reject_mixing() -> (
    None
):
    result = prepare_profile_group(
        data(), ProfileRequest(DistributionSettings(("a", "b"), standardize=True))
    )
    a, b = result.profiles.columns
    assert a.statistics and a.statistics.mean == pytest.approx(2)
    assert b.statistics and b.statistics.mean == pytest.approx(20)
    assert result.comparison is not None
    assert result.comparison.series[0].ecdf_x[1] == pytest.approx(0)
    for columns in (("a", "cat"), ("text",), ("row_id",)):
        with pytest.raises(ValueError, match="Choose one"):
            prepare_profile_group(data(), ProfileRequest(DistributionSettings(columns)))
    category = prepare_profile_group(
        data(), ProfileRequest(DistributionSettings(("cat",)))
    )
    assert category.comparison is None and category.bars[0].counts.tolist() == [2, 1]


def test_unrepresentable_plot_keeps_exact_statistics_and_histogram_fallback() -> None:
    dataset = Dataset.from_source(
        pl.DataFrame({"x": [-1e308, 1e308]}), SourceReference(Path("unused"), 0, 0)
    )
    result = prepare_profile_group(
        dataset, ProfileRequest(DistributionSettings(("x",)))
    )
    assert result.comparison is None and "overflows" in result.message
    assert result.profiles.columns[0].statistics is not None
    assert result.profiles.columns[0].statistics.mean == 0
    assert result.bars[0].counts.sum() == 2


def test_selection_recipe_roundtrip_and_legacy_default() -> None:
    for columns in (("b", "a"), (), ("cat",), ("text",)):
        saved = WorkspaceViews(
            profile_selection=columns, profile_mode=2, profile_text=True
        )
        saved.validate()
        assert decode_record(WorkspaceViews, encode(saved)) == saved
    assert (
        decode_record(WorkspaceViews, {"kind": "WorkspaceViews"}).profile_selection
        is None
    )
    assert not decode_record(WorkspaceViews, {"kind": "WorkspaceViews"}).profile_text
    with pytest.raises(ValueError, match="distinct"):
        WorkspaceViews(profile_selection=("a", "a")).validate()
