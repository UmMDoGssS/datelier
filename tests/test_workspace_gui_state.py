"""Semantic GUI settings restore independently of a graphics context."""

from dataclasses import replace
from pathlib import Path

from datelier.analysis.types import (
    Algorithm,
    AnalysisRequest,
    Preprocessing,
    TSNEParameters,
)
from datelier.gui.analysis.controls import AnalysisControls
from datelier.gui.plots.controls import PlotControls
from datelier.gui.profiles.view import profile_summary
from datelier.gui.workspace.state import restore_analysis, restore_plots
from datelier.inspection.exploration import PlotSettings
from datelier.inspection.profiles import prepare_profiles
from datelier.io.importing import load_file
from datelier.plotting.distributions import DistributionSettings
from datelier.workspace.codec import decode_record, encode
from datelier.workspace.storage import reference_source
from datelier.workspace.types import Workspace, WorkspaceViews


def test_plot_names_restore_independently_of_column_order(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("z,y,x,group\n3.0,2,1,a\n4.0,3,2,b\n5.0,4,3,a\n")
    dataset = load_file(path).dataset
    saved = PlotSettings(
        bins=7,
        point_limit=100,
        scatter_pair=("x", "y"),
        scatter_z="z",
        profile_column="group",
        comparison=DistributionSettings(("x", "z"), True, False, 2, 17),
        color_column="group",
        relationship_features=("z", "x"),
    )
    controls = PlotControls()
    assert not restore_plots(controls, dataset, saved)
    assert controls.settings() == saved
    assert controls.three_d and controls.custom_scatter


def test_removed_columns_reset_only_unavailable_views(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("x,y\n1.0,2\n3.0,4\n")
    dataset = load_file(path).dataset
    saved = PlotSettings(
        bins=9,
        scatter_pair=("x", "missing"),
        scatter_z="gone",
        profile_column="gone",
        color_column="gone",
        comparison=DistributionSettings(("x", "missing")),
        relationship_features=("x", "gone"),
    )
    controls = PlotControls()
    assert restore_plots(controls, dataset, saved)
    result = controls.settings()
    assert result.bins == 9
    assert result.scatter_pair is None and result.scatter_z is None
    assert result.profile_column is None and result.color_column is None
    assert result.comparison.columns == ("x",)
    assert result.relationship_features == ("x",)


def test_analysis_controls_round_trip_without_launching_jobs(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("x,y\n1.0,2\n3.0,4\n")
    imported = load_file(path)
    before = AnalysisControls(
        features=["y", "x"],
        standardize=False,
        impute=True,
        dimensions=3,
        seed=19,
        pca_whiten=True,
        pca_solver=1,
        perplexity=4,
        tsne_auto_rate=False,
        tsne_rate=55,
        tsne_init=1,
        umap_metric=1,
        neighbors=7,
        clusters=5,
    )
    requests = tuple(before.request(a) for a in Algorithm)
    workspace = Workspace(
        reference_source(imported.dataset.source),
        imported.format,
        imported.options,
        analysis=requests,
    )
    after = AnalysisControls()
    restore_analysis(after, workspace, imported.dataset)
    assert tuple(after.request(a) for a in Algorithm) == requests
    workspace = replace(
        workspace,
        analysis=(
            AnalysisRequest(
                ("x", "gone"), TSNEParameters(5), Preprocessing(False, True)
            ),
        ),
    )
    restore_analysis(after, workspace, imported.dataset)
    assert after.features == ["x"]


def test_profile_chart_type_recipes_remain_backward_compatible() -> None:
    old = decode_record(WorkspaceViews, {"kind": "WorkspaceViews", "profile_index": 4})
    assert old.profile_mode == 0
    assert old.coordinate_source is None
    saved = WorkspaceViews(
        profile_mode=2, profile_index=4, coordinate_source=Algorithm.PCA
    )
    assert decode_record(WorkspaceViews, encode(saved)) == saved
    saved.validate()


def test_unfitted_coordinates_survive_polling_without_starting_analysis(
    tmp_path: Path,
) -> None:
    from datelier.gui.analysis.session import AnalysisSession

    source = tmp_path / "data.csv"
    source.write_text("x,y,z\n1.0,2,3\n3.0,4,5\n")
    data = load_file(source).dataset
    session = AnalysisSession(source=Algorithm.PCA)
    plots = PlotControls(three_d=True, custom_scatter=True)
    plots.bind(data)
    plots.custom_scatter = True
    try:
        assert not session.poll(data)
        assert session.source == Algorithm.PCA
        assert not session.jobs.busy and not session.jobs.results
        assert plots.three_d and plots.settings().scatter_z == "z"
        session.source = None
        assert not session.poll(data)
        assert session.source is None and plots.three_d
    finally:
        session.close()


def test_manual_axes_can_swap_without_duplicate_coordinates() -> None:
    controls = PlotControls(numeric=("x", "y"))
    controls.choose_axis("x_index", 1)
    assert (controls.x_index, controls.y_index) == (1, 0)
    controls.numeric = ("x", "y", "z")
    controls.three_d = True
    controls.choose_axis("x_index", 2)
    assert (controls.x_index, controls.y_index, controls.z_index) == (2, 0, 1)


def test_profile_summary_accounts_for_missing_and_nonfinite(tmp_path: Path) -> None:
    import polars as pl

    from datelier.core.dataset import Dataset, SourceReference

    data = Dataset.from_source(
        pl.DataFrame({"x": [1.0, 2.0, None, float("inf")]}),
        SourceReference(tmp_path / "unused", 0, 0),
    )
    profile = prepare_profiles(data).columns[0]
    assert profile_summary(profile, 4) == "2 included · 1 missing (25.0%) · 1 nonfinite"


def test_color_sources_are_exclusive_and_selection_does_not_run_ml(
    tmp_path: Path,
) -> None:
    from datelier.gui.analysis.session import AnalysisSession

    path = tmp_path / "data.csv"
    path.write_text("x,y,group\n1.0,2,a\n3.0,4,b\n5.0,6,a\n")
    dataset = load_file(path).dataset
    plots = PlotControls()
    plots.bind(dataset)
    analysis = AnalysisSession()
    try:
        plots.choose_color("Column")
        plots.color_index = plots.color_columns.index("group") + 1
        assert plots.settings().color_column == "group"
        plots.choose_color("K-means")
        assert plots.cluster_algorithm == Algorithm.KMEANS
        assert plots.settings().color_column is None
        assert plots.settings().clusters is None
        assert analysis.selected_algorithm(plots) == Algorithm.KMEANS
        assert not analysis.jobs.busy and not analysis.jobs.results
        plots.choose_color("Uniform")
        assert plots.settings().color_column is None
        plots.choose_color("Column")
        assert plots.color_column == "group"
        plots.bind(dataset)
        assert plots.color_source == "Column" and plots.color_column == "group"
    finally:
        analysis.close()


def test_unfitted_color_source_is_saved_without_fitted_artifacts() -> None:
    saved = WorkspaceViews(color_source="K-means")
    saved.validate()
    assert decode_record(WorkspaceViews, encode(saved)) == saved


def test_every_method_recipe_round_trips_through_strict_codec(tmp_path: Path) -> None:
    from datelier.analysis.embedding_parameters import LLEParameters
    from datelier.analysis.parameters import DBSCANParameters

    path = tmp_path / "data.csv"
    path.write_text("x,y,z\n1.0,2,3\n3.0,4,5\n6.0,8,9\n")
    imported = load_file(path)
    before = AnalysisControls(features=["z", "x", "y"], dimensions=3, seed=19)
    before.extra_parameters[Algorithm.DBSCAN] = DBSCANParameters(epsilon=0.75)
    before.extra_parameters[Algorithm.LLE] = LLEParameters(
        method="hessian", neighbors=20
    )
    requests = tuple(before.request(a) for a in Algorithm)
    saved = Workspace(
        reference_source(imported.dataset.source),
        imported.format,
        imported.options,
        analysis=requests,
        views=WorkspaceViews(coordinate_source=Algorithm.LLE, color_source="DBSCAN"),
    )
    saved.validate()
    decoded = decode_record(Workspace, encode(saved))
    decoded.validate()
    assert decoded == saved
    after = AnalysisControls()
    restore_analysis(after, decoded, imported.dataset)
    assert tuple(after.request(a) for a in Algorithm) == requests


def test_finished_clustering_cannot_override_another_color_source(
    tmp_path: Path,
) -> None:
    from datelier.analysis.input import prepare_input
    from datelier.analysis.runner import run_analysis
    from datelier.analysis.types import ClusteringResult, KMeansParameters
    from datelier.gui.analysis.session import AnalysisSession

    path = tmp_path / "data.csv"
    path.write_text("x,y,group\n0,1,a\n1,0,a\n9,10,b\n10,9,b\n")
    dataset = load_file(path).dataset
    result = run_analysis(
        prepare_input(dataset, AnalysisRequest(("x", "y"), KMeansParameters(2)))
    )
    assert isinstance(result, ClusteringResult)
    analysis = AnalysisSession()
    plots = PlotControls()
    plots.bind(dataset)
    try:
        plots.choose_color("K-means")
        analysis.jobs.results[Algorithm.KMEANS] = result
        assert analysis.sync_colors(plots)
        assert plots.settings().clusters is result
        plots.choose_color("Uniform")
        assert not analysis.sync_colors(plots)
        assert plots.settings().clusters is None and plots.color_source == "Uniform"
        plots.choose_color("Column")
        assert not analysis.sync_colors(plots)
        assert plots.settings().clusters is None and plots.color_column is not None
        plots.choose_color("K-means")
        assert analysis.sync_colors(plots)
        plots.bind(load_file(path).dataset)
        analysis.poll(load_file(path).dataset)
        analysis.sync_colors(plots)
        assert plots.color_source == "K-means" and plots.cluster_result is None
    finally:
        analysis.close()


def test_column_color_survives_removal_of_the_selected_column(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("x,y,group\n1.0,2,a\n3.0,4,b\n5.0,6,a\n")
    plots = PlotControls()
    plots.bind(load_file(path).dataset)
    plots.choose_color("Column")
    plots.color_index = plots.color_columns.index("group") + 1
    path.write_text("x,y\n1.0,2\n3.0,4\n")
    plots.bind(load_file(path).dataset)
    assert plots.color_source == "Column" and plots.settings().color_column == "x"


def test_coordinate_dimension_changes_do_not_invalidate_clustering_settings() -> None:
    controls = AnalysisControls(features=["x", "y", "z"])
    clustering = controls.request(Algorithm.DBSCAN)
    embedding = controls.request(Algorithm.PCA)
    controls.dimensions = 3
    assert controls.matches_result(clustering)
    assert not controls.matches_result(embedding)
    controls.features.remove("z")
    assert not controls.matches_result(clustering)


def test_pending_default_correlations_preserve_saved_pair_grid(
    tmp_path: Path, monkeypatch
) -> None:
    from imgui_bundle import imgui

    from datelier.gui.data.table import TableView
    from datelier.gui.exploration import ExplorationView
    from datelier.inspection.exploration import Explorer
    from datelier.plotting.selection import LinkedSelection

    source = tmp_path / "data.csv"
    source.write_text("x,y\n1.0,2\n3.0,4\n5.0,6\n")
    dataset = load_file(source).dataset
    plots = PlotControls()
    plots.bind(dataset)
    plots.relationship_features = []  # A legacy empty recipe uses numeric defaults.
    view = ExplorationView(tab="Correlations", active_tab="Correlations")
    view.relationships.mode = 1
    monkeypatch.setattr(imgui, "get_window_dock_id", lambda: 0)
    monkeypatch.setattr(imgui, "text_wrapped", lambda _text: None)
    monkeypatch.setattr(imgui, "begin_table", lambda *_args: False)
    monkeypatch.setattr(imgui, "begin_tab_bar", lambda _label: True)
    monkeypatch.setattr(
        imgui,
        "begin_tab_item",
        lambda label, **_kwargs: (label == "Correlations", None),
    )
    monkeypatch.setattr(imgui, "end_tab_item", lambda: None)
    monkeypatch.setattr(imgui, "end_tab_bar", lambda: None)
    explorer = Explorer()
    try:
        view.show(explorer, LinkedSelection(), TableView(), plots, dataset)
        assert view.relationships.mode == 1
    finally:
        explorer.close()
