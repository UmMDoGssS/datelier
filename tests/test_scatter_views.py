from pathlib import Path

import polars as pl
import pytest

from datelier.analysis_types import Algorithm
from datelier.core.dataset import Dataset, SourceReference
from datelier.exploration import PlotSettings
from datelier.gui_analysis import AnalysisSession
from datelier.gui_plot_controls import PlotControls
from datelier.gui_workspace_state import restore_plots
from datelier.recipe_codec import decode_record, encode
from datelier.workspace_types import WorkspaceViews


def data() -> Dataset:
    return Dataset.from_source(
        pl.DataFrame({"x": [1, 2, 3], "y": [3, 1, 2], "z": [2, 3, 1]}),
        SourceReference(Path("unused"), 0, 0),
    )


@pytest.mark.parametrize("dimensions", [2, 3])
def test_every_reduction_follows_the_plot_without_launching_analysis(
    dimensions: int,
) -> None:
    plots = PlotControls()
    plots.bind(data())
    analysis = AnalysisSession()
    try:
        analysis.controls.features = list(plots.numeric)
        plots.choose_chart(f"Scatter {dimensions}D")
        analysis.sync_dimensions(plots)
        for algorithm in Algorithm:
            if not algorithm.is_clustering:
                analysis.source = algorithm
                assert analysis.controls.request(algorithm).dimensions == dimensions
        assert plots.chart_choice == f"Scatter {dimensions}D"
        assert not analysis.jobs.busy and not analysis.jobs.results
        plots.choose_chart("Box")
        assert plots.three_d == (dimensions == 3)
    finally:
        analysis.close()


def test_separate_scatter_choices_preserve_distinct_raw_axes_and_colors() -> None:
    plots = PlotControls()
    plots.bind(data())
    plots.choose_color("K-means")
    plots.z_index = plots.x_index
    plots.choose_chart("Scatter 3D")
    saved = plots.settings()
    assert len(set((*(saved.scatter_pair or ()), saved.scatter_z))) == 3
    plots.choose_chart("Scatter 2D")
    assert plots.settings().scatter_z is None
    assert plots.color_source == "K-means"
    assert plots.scatter_dirty
    plots.choose_chart("Scatter 3D")
    assert plots.settings() == saved


def test_legacy_raw_scatter_recipes_keep_their_dimension() -> None:
    plots = PlotControls()
    saved = PlotSettings(scatter_pair=("x", "y"), scatter_z="z")
    assert not restore_plots(plots, data(), saved)
    assert plots.chart_choice == "Scatter 3D"
    plots.choose_chart("Scatter 2D")
    assert plots.settings().scatter_pair == ("x", "y")


def test_scatter_view_recipes_keep_both_heights_and_decode_legacy_defaults() -> None:
    saved = WorkspaceViews(
        tab="Relationships",
        scatter_dimensions=3,
        scatter_height=220,
        scatter3d_height=310,
    )
    saved.validate()
    assert decode_record(WorkspaceViews, encode(saved)) == saved
    old = decode_record(
        WorkspaceViews, {"kind": "WorkspaceViews", "scatter_height": 240}
    )
    assert old.scatter_dimensions is None and old.scatter3d_height == 0
    for dimensions in (1, 4):
        with pytest.raises(ValueError, match="dimensions"):
            WorkspaceViews(scatter_dimensions=dimensions).validate()
    for height in (150, float("nan")):
        with pytest.raises(ValueError, match="heights"):
            WorkspaceViews(scatter3d_height=height).validate()
