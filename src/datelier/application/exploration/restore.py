"""Restore schema-bound semantic settings independently of native rendering."""

from dataclasses import replace

from datelier.application.analysis import AnalysisSettings
from datelier.application.exploration.plots import PlotState
from datelier.core import Dataset
from datelier.inspection.exploration import PlotSettings
from datelier.plotting.categories import CategoryRepresentation
from datelier.workspace.single import Workspace


def restore_plots(controls: PlotState, dataset: Dataset, saved: PlotSettings) -> bool:
    controls.bind(dataset)
    controls.profile_redirect = None
    for name in (
        "profile_columns",
        "bins",
        "top_counts",
        "correlation_columns",
        "point_limit",
        "diagonal_mode",
    ):
        setattr(controls, name, getattr(saved, name))
    pair = saved.scatter_pair
    valid_pair = (
        pair is not None
        and len(set(pair)) == 2
        and all(n in controls.numeric for n in pair)
    )
    controls.custom_scatter = valid_pair
    if valid_pair:
        assert pair is not None
        controls.x_index, controls.y_index = (controls.numeric.index(n) for n in pair)
    controls.three_d = (
        valid_pair
        and saved.scatter_z in controls.numeric
        and saved.scatter_z not in (pair or ())
    )
    if controls.three_d:
        assert saved.scatter_z is not None
        controls.z_index = controls.numeric.index(saved.scatter_z)
    controls.profile_index = (
        controls.columns.index(saved.profile_column) + 1
        if saved.profile_column in controls.columns
        else 0
    )
    controls.color_index = (
        controls.color_columns.index(saved.color_column) + 1
        if saved.color_column in controls.color_columns
        else 0
    )
    controls.choose_color("Column" if controls.color_index else "Uniform")
    controls.compare_columns = [
        n for n in saved.comparison.columns if n in controls.numeric
    ]
    controls.relationship_features = [
        n for n in saved.relationship_features if n in controls.numeric
    ]
    comparison = saved.comparison
    controls.standardize, controls.density = comparison.standardize, comparison.density
    controls.bandwidth, controls.seed = comparison.bandwidth, comparison.seed
    controls.relationship_chart = "Scatter"
    if saved.category_chart is not None:
        chart = saved.category_chart
        if (
            chart.category in controls.categories
            and (chart.group is None or chart.group in controls.categories)
            and (chart.value is None or chart.value in controls.numeric)
        ):
            if chart.representation == CategoryRepresentation.COUNTS:
                controls.profile_redirect = chart.category
                controls.profile_index = controls.columns.index(chart.category) + 1
            else:
                controls.relationship_chart = chart.representation.value
                if chart.representation in (
                    CategoryRepresentation.BOX,
                    CategoryRepresentation.VIOLIN,
                ):
                    controls.bandwidth, controls.seed = chart.bandwidth, chart.seed
            (
                controls.category_column,
                controls.category_group,
                controls.category_value,
            ) = chart.category, chart.group, chart.value
            controls.top_counts = chart.top
    return controls.settings() != replace(saved, clusters=None)


def restore_analysis(
    controls: AnalysisSettings, workspace: Workspace, dataset: Dataset
) -> None:
    if not workspace.analysis:
        controls.bind(dataset)
        return
    common = workspace.analysis[0]
    controls.bind(dataset)
    controls.features = [n for n in common.features if n in controls.numeric]
    controls.standardize = common.preprocessing.standardize
    controls.impute = common.preprocessing.impute
    controls.dimensions, controls.seed = common.dimensions, common.seed
    for request in workspace.analysis:
        controls.restore(request)
