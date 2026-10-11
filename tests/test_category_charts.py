from dataclasses import replace
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from datelier.application.exploration import PlotState
from datelier.application.exploration.restore import restore_plots
from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset, SourceReference
from datelier.inspection.exploration import PlotSettings
from datelier.pipeline.operations import Sort, apply_operation
from datelier.plotting.categories import CategoryRepresentation as Mode
from datelier.plotting.categories import CategorySettings, prepare_category_chart
from datelier.workspace.recipes.codec import decode_record, encode


def data() -> Dataset:
    return Dataset.from_source(
        pl.DataFrame(
            {
                "category": ["a", "a", "b", "b", None, "Missing (null)"],
                "group": ["x", "y", "x", "y", "x", "x"],
                "value": [1.0, 3.0, 6.0, float("inf"), None, -2.0],
            }
        ),
        SourceReference(Path("unused"), 0, 0),
    )


def test_counts_grouping_missing_and_other_keep_all_rows() -> None:
    dataset = apply_operation(data(), Sort(("value",), descending=True))
    chart = prepare_category_chart(dataset, CategorySettings("category", top=1))
    assert chart.values.tolist() == [[2.0, 4.0]]
    assert chart.labels == ("a", "Other (remaining values)")
    assert chart.other_categories == 3
    assert sum(len(ids) for row in chart.row_ids for ids in row) == 6
    assert set(i for row in chart.row_ids for ids in row for i in ids) == set(range(6))
    for g, row in enumerate(chart.first_positions):
        for c, position in enumerate(row):
            if chart.counts[g, c]:
                assert dataset.row_ids[position] in chart.row_ids[g][c]
    grouped = prepare_category_chart(
        dataset, CategorySettings("category", Mode.GROUPED, group="group")
    )
    assert grouped.values.sum() == 6 and len(grouped.groups) == 2
    assert len(set(grouped.labels)) == len(grouped.labels)
    assert not chart.values.flags.writeable and not chart.counts.flags.writeable


@pytest.mark.parametrize(
    "mode,expected", [(Mode.MEAN, 2), (Mode.MEDIAN, 2), (Mode.SUM, 4)]
)
def test_numeric_aggregation_excludes_nonfinite_values(
    mode: Mode, expected: float
) -> None:
    chart = prepare_category_chart(
        data(), CategorySettings("category", mode, value="value")
    )
    assert chart.excluded_values == 2 and chart.included_rows == 4
    assert chart.values[0, chart.labels.index("a")] == expected
    assert chart.counts.sum() == 4
    assert chart.values[0, chart.labels.index("Missing (null)")] == -2
    assert np.isfinite(chart.values).all()


def test_role_compatibility_saved_controls_and_unique_text_exclusion() -> None:
    dataset = data()
    settings = PlotSettings(
        category_chart=CategorySettings("category", Mode.BOX, value="value")
    )
    assert decode_record(PlotSettings, encode(settings)) == settings
    plots = PlotState()
    assert not restore_plots(plots, dataset, settings)
    assert plots.category_settings() == settings.category_chart
    with pytest.raises(ValueError):
        prepare_category_chart(dataset, CategorySettings("value"))
    with pytest.raises(ValueError):
        CategorySettings("category", Mode.GROUPED, group="category").validate()
    with pytest.raises(ValueError):
        CategorySettings("category", Mode.COUNTS, value="value").validate()
    text = dataset.with_role("category", ColumnRole.TEXT)
    plots.bind(text)
    assert "category" not in plots.categories
    assert restore_plots(plots, text, settings)
    assert plots.relationship_chart == "Scatter"


def test_empty_high_cardinality_and_bounded_bar_selection() -> None:
    dataset = Dataset.from_source(
        pl.DataFrame({"category": ["a"] * 20_000}),
        SourceReference(Path("unused"), 0, 0),
    )
    chart = prepare_category_chart(dataset, CategorySettings("category"))
    assert chart.counts.sum() == 20_000
    assert len(chart.row_ids[0][0]) == 10_000
    empty = dataset.with_rows(dataset.table.clear(), dataset.row_ids.clear())
    assert not prepare_category_chart(empty, CategorySettings("category")).labels
    wide = Dataset.from_source(
        pl.DataFrame(
            {
                "category": [str(i % 40) for i in range(100_010)],
                "group": [str(i % 7) for i in range(100_010)],
            }
        ),
        SourceReference(Path("unused"), 0, 0),
    )
    grouped = prepare_category_chart(
        wide, CategorySettings("category", Mode.GROUPED, group="group")
    )
    assert grouped.input_rows == grouped.included_rows == 100_000
    assert grouped.values.shape == (6, 13)
    assert grouped.values.sum() == 100_000
    assert grouped.other_categories == 28 and grouped.other_groups == 2
    assert replace(CategorySettings("category"), top=31)
    with pytest.raises(ValueError):
        replace(CategorySettings("category"), top=31).validate()


@pytest.mark.parametrize("mode", [Mode.BOX, Mode.VIOLIN, Mode.GROUPED])
def test_category_recipe_survives_workspace_replay_and_view_restore(
    tmp_path: Path,
    mode: Mode,
) -> None:
    from datelier.io.importing import load_file
    from datelier.workspace.single import Workspace, WorkspaceViews
    from datelier.workspace.single.restore import restore_workspace
    from datelier.workspace.single.storage import reference_source, save_workspace

    source = tmp_path / "data.csv"
    source.write_text("group,other,value\na,x,1\nb,y,2\na,x,3\n")
    imported = load_file(source)
    plots = PlotSettings(
        category_chart=CategorySettings(
            "group",
            mode,
            value="value" if mode != Mode.GROUPED else None,
            group="other" if mode == Mode.GROUPED else None,
        )
    )
    workspace = Workspace(
        reference_source(imported.dataset.source),
        imported.format,
        imported.options,
        plots=plots,
        views=WorkspaceViews(tab="Relationships", category_height=310),
    )
    saved = tmp_path / "charts.datelier"
    save_workspace(saved, workspace)
    restored = restore_workspace(saved)
    assert restored.workspace.plots == plots
    assert restored.workspace.views.category_height == 310
    controls = PlotState()
    assert not restore_plots(
        controls, restored.pipeline.current, restored.workspace.plots
    )
    assert controls.relationship_chart == mode.value


@pytest.mark.parametrize("mode", [Mode.MEAN, Mode.MEDIAN, Mode.SUM])
def test_numeric_aggregate_recipes_restore_their_original_representation(
    mode: Mode,
) -> None:
    saved = PlotSettings(
        category_chart=CategorySettings("category", mode, value="value", top=4)
    )
    controls = PlotState()
    restore_plots(controls, data(), decode_record(PlotSettings, encode(saved)))
    assert controls.category_settings() == CategorySettings(
        "category", mode, value="value", top=4
    )
    assert controls.profile_redirect is None


def test_legacy_single_column_bars_route_to_profiles() -> None:
    saved = PlotSettings(category_chart=CategorySettings("group", top=5))
    controls = PlotState()
    dataset = data()
    assert restore_plots(controls, dataset, saved)
    assert controls.settings().category_chart is None
    assert controls.profile_redirect == "group"
    assert controls.columns[controls.profile_index - 1] == "group"
    assert controls.top_counts == 5
    removed = dataset.with_role("group", ColumnRole.TEXT)
    controls = PlotState()
    assert restore_plots(controls, removed, saved)
    assert controls.profile_redirect is None


def test_category_density_settings_restore_with_provenance() -> None:
    from datelier.plotting.distributions import DistributionSettings

    saved = PlotSettings(
        comparison=DistributionSettings(bandwidth=0.75, seed=17),
        category_chart=CategorySettings(
            "category", Mode.VIOLIN, value="value", bandwidth=0.75, seed=17
        ),
    )
    controls = PlotState()
    assert not restore_plots(controls, data(), saved)
    assert controls.settings() == saved


def test_numeric_axes_remain_distinct_after_a_role_change() -> None:
    dataset = Dataset.from_source(
        pl.DataFrame({"a": [1, 2, 3], "b": [2, 3, 4], "c": [3, 4, 5], "d": [4, 5, 6]}),
        SourceReference(Path("unused"), 0, 0),
    )
    controls = PlotState(three_d=True)
    controls.bind(dataset)
    controls.bind(dataset.with_role("a", ColumnRole.CATEGORY))
    assert len(set((controls.x_index, controls.y_index, controls.z_index))) == 3
    controls.settings().validate()


def test_extreme_aggregates_do_not_publish_infinite_bar_values() -> None:
    dataset = Dataset.from_source(
        pl.DataFrame({"group": ["a", "a"], "value": [1e308, 1e308]}),
        SourceReference(Path("unused"), 0, 0),
    )
    chart = prepare_category_chart(
        dataset, CategorySettings("group", Mode.MEAN, value="value")
    )
    assert chart.values[0, 0] == pytest.approx(1e308)
    with pytest.raises(ValueError, match="overflowed"):
        prepare_category_chart(
            dataset, CategorySettings("group", Mode.SUM, value="value")
        )
