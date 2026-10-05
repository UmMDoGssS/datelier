"""Translate saved semantic settings into schema-bound GUI controls."""

from dataclasses import replace
from typing import TYPE_CHECKING

from datelier.analysis.parameters import EXTRA_DEFAULTS
from datelier.analysis.types import (
    KMeansParameters,
    PCAParameters,
    TSNEParameters,
    UMAPParameters,
)
from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset
from datelier.gui_analysis_controls import AnalysisControls
from datelier.gui_plot_controls import PlotControls
from datelier.inspection.exploration import PlotSettings
from datelier.plotting.categories import CategoryRepresentation
from datelier.workspace.types import Workspace, WorkspaceViews

if TYPE_CHECKING:
    from datelier.gui import GuiSession


def restore_plots(
    controls: PlotControls, dataset: Dataset, saved: PlotSettings
) -> bool:
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
                controls.relationship_chart = (
                    CategoryRepresentation.BOX.value
                    if chart.representation
                    in (
                        CategoryRepresentation.MEAN,
                        CategoryRepresentation.MEDIAN,
                        CategoryRepresentation.SUM,
                    )
                    else chart.representation.value
                )
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
    controls: AnalysisControls, workspace: Workspace, dataset: Dataset
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
        params = request.parameters
        if isinstance(params, PCAParameters):
            controls.pca_limit = request.row_limit
            controls.pca_solver = ["randomized", "full"].index(params.solver)
            controls.pca_whiten = params.whiten
        elif isinstance(params, TSNEParameters):
            controls.tsne_limit = request.row_limit
            controls.perplexity, controls.tsne_iterations = (
                params.perplexity,
                params.iterations,
            )
            controls.tsne_auto_rate = params.learning_rate == "auto"
            if isinstance(params.learning_rate, (int, float)):
                controls.tsne_rate = float(params.learning_rate)
            controls.tsne_init = ["pca", "random"].index(params.initialization)
        elif isinstance(params, UMAPParameters):
            controls.umap_limit = request.row_limit
            controls.neighbors, controls.min_distance = (
                params.neighbors,
                params.min_distance,
            )
            controls.umap_metric = ["euclidean", "cosine"].index(params.metric)
        elif isinstance(params, KMeansParameters):
            controls.kmeans_limit = request.row_limit
            controls.clusters = params.clusters
            controls.initializations = params.initializations
            controls.kmeans_iterations = params.iterations
        elif request.algorithm in EXTRA_DEFAULTS:
            controls.extra_parameters[request.algorithm] = params
            controls.extra_limits[request.algorithm] = request.row_limit


def capture_views(session: GuiSession) -> WorkspaceViews:
    view = session.exploration
    return WorkspaceViews(
        view.active_tab,
        view.comparison_mode,
        view.relationships.mode,
        view.profile_index,
        view.scatter_index,
        session.table.column_start,
        session.table.target_row,
        view.profile_mode,
        session.analysis.source,
        view.profile.area.height,
        view.comparison_area.height,
        view.scatter_area.height,
        view.relationships.area.height,
        session.plots.color_source,
        view.categories.area.height,
        view.profile.selection.columns,
        session.plots.scatter_dimensions,
        view.scatter3d_area.height,
    )


def restore_views(session: GuiSession, workspace: Workspace) -> bool:
    assert session.loader.active is not None
    dataset = session.loader.active.dataset
    adjusted = restore_plots(session.plots, dataset, workspace.plots)
    restore_analysis(session.analysis.controls, workspace, dataset)
    restore_view_settings(session, workspace.views)
    if workspace.views.profile_selection is not None:
        adjusted |= (
            session.exploration.profile.selection.columns
            != workspace.views.profile_selection
        )
    return adjusted


def restore_view_settings(session: GuiSession, saved: WorkspaceViews) -> None:
    assert session.loader.active is not None
    dataset = session.loader.active.dataset
    view = session.exploration
    dimensions = saved.scatter_dimensions or (
        session.analysis.controls.dimensions
        if saved.coordinate_source is not None
        else session.plots.scatter_dimensions
    )
    session.plots.three_d = dimensions == 3
    session.analysis.sync_dimensions(session.plots)
    view.tab = view.active_tab = (
        "Relationships" if saved.tab == "Scatter" else saved.tab
    )
    view.comparison_mode, view.relationships.mode = (
        saved.comparison_mode,
        saved.relationship_mode,
    )
    view.profile_index = saved.profile_index
    view.profile_mode = saved.profile_mode
    view.profile.selection.columns = saved.profile_selection
    legacy_comparison = (
        saved.profile_selection is None
        and session.plots.compare_columns
        and saved.comparison_mode < 5
    )
    if legacy_comparison:
        view.profile.selection.columns = tuple(session.plots.compare_columns)
        view.profile_mode = saved.comparison_mode
    legacy_names = tuple(
        i.name
        for i in dataset.roles or ()
        if i.role not in (ColumnRole.TEXT, ColumnRole.IDENTIFIER)
    )
    default = (
        session.plots.columns[session.plots.profile_index - 1]
        if session.plots.profile_index
        else legacy_names[min(saved.profile_index, len(legacy_names) - 1)]
        if legacy_names
        else None
    )
    view.profile.selection.bind(dataset, default)
    redirect = session.plots.profile_redirect
    if redirect is not None:
        view.profile.selection.columns = (redirect,)
        if view.active_tab == "Relationships":
            view.tab = view.active_tab = "Profiles"
        session.plots.profile_redirect = None
    session.analysis.source = saved.coordinate_source
    if saved.color_source is not None:
        session.plots.choose_color(saved.color_source)
    view.profile.area.height = saved.profile_height or (
        saved.comparison_height if legacy_comparison else 0
    )
    if redirect is not None and saved.tab in ("Scatter", "Relationships"):
        view.profile.area.height = saved.category_height or saved.profile_height
    view.comparison_area.height = saved.comparison_height
    view.scatter_area.height = saved.scatter_height
    view.scatter3d_area.height = saved.scatter3d_height or (
        saved.scatter_height
        if saved.scatter_dimensions is None and dimensions == 3
        else 0
    )
    view.relationships.area.height = saved.relationship_height
    view.categories.area.height = saved.category_height
    view.saved_scatter_index = saved.scatter_index
    session.table.column_start = min(saved.column_start, dataset.table.width - 1)
    session.table.target_row = min(saved.target_row, max(1, dataset.table.height))
    session.table.jump = True
