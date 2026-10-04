"""Semantic GUI settings restore independently of a graphics context."""

from dataclasses import replace
from pathlib import Path

from datelier.analysis_types import (
    Algorithm,
    AnalysisRequest,
    Preprocessing,
    TSNEParameters,
)
from datelier.distributions import DistributionSettings
from datelier.exploration import PlotSettings
from datelier.gui_analysis_controls import AnalysisControls
from datelier.gui_plot_controls import PlotControls
from datelier.gui_profiles import profile_summary
from datelier.gui_workspace_state import restore_analysis, restore_plots
from datelier.importing import load_file
from datelier.profiling import prepare_profiles
from datelier.recipe_codec import decode_record, encode
from datelier.workspace_types import Workspace, WorkspaceViews
from datelier.workspaces import reference_source


def test_plot_names_restore_independently_of_column_order(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("z,y,x,group\n3,2,1,a\n4,3,2,b\n")
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
    path.write_text("x,y\n1,2\n3,4\n")
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
    path.write_text("x,y\n1,2\n3,4\n")
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
    from datelier.gui_analysis import AnalysisSession

    source = tmp_path / "data.csv"
    source.write_text("x,y,z\n1,2,3\n3,4,5\n")
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

    from datelier.dataset import Dataset, SourceReference

    data = Dataset.from_source(
        pl.DataFrame({"x": [1.0, 2.0, None, float("inf")]}),
        SourceReference(tmp_path / "unused", 0, 0),
    )
    profile = prepare_profiles(data).columns[0]
    assert profile_summary(profile, 4) == "2 included · 1 missing (25.0%) · 1 nonfinite"
