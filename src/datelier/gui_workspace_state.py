"""Translate saved semantic settings into schema-bound GUI controls."""

from dataclasses import replace
from typing import TYPE_CHECKING

from datelier.analysis_types import (
    KMeansParameters,
    PCAParameters,
    TSNEParameters,
    UMAPParameters,
)
from datelier.dataset import Dataset
from datelier.exploration import PlotSettings
from datelier.gui_analysis_controls import AnalysisControls
from datelier.gui_plot_controls import PlotControls
from datelier.workspace_types import Workspace, WorkspaceViews

if TYPE_CHECKING:
    from datelier.gui import GuiSession


def restore_plots(
    controls: PlotControls, dataset: Dataset, saved: PlotSettings
) -> bool:
    controls.bind(dataset)
    for name in (
        "profile_columns",
        "bins",
        "top_counts",
        "correlation_columns",
        "point_limit",
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
    )


def restore_views(session: GuiSession, workspace: Workspace) -> bool:
    assert session.loader.active is not None
    dataset = session.loader.active.dataset
    adjusted = restore_plots(session.plots, dataset, workspace.plots)
    restore_analysis(session.analysis.controls, workspace, dataset)
    restore_view_settings(session, workspace.views)
    return adjusted


def restore_view_settings(session: GuiSession, saved: WorkspaceViews) -> None:
    assert session.loader.active is not None
    dataset = session.loader.active.dataset
    view = session.exploration
    view.tab = view.active_tab = saved.tab
    view.comparison_mode, view.relationships.mode = (
        saved.comparison_mode,
        saved.relationship_mode,
    )
    view.profile_index = saved.profile_index
    view.profile_mode = saved.profile_mode
    session.analysis.source = saved.coordinate_source
    if saved.color_source is not None:
        session.plots.choose_color(saved.color_source)
    view.profile.area.height = saved.profile_height
    view.comparison_area.height = saved.comparison_height
    view.scatter_area.height = saved.scatter_height
    view.relationships.area.height = saved.relationship_height
    view.saved_scatter_index = saved.scatter_index
    session.table.column_start = min(saved.column_start, dataset.table.width - 1)
    session.table.target_row = min(saved.target_row, max(1, dataset.table.height))
    session.table.jump = True
