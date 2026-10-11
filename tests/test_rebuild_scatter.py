"""Independent scatter dimensions, fitted coordinate sources and idle restoration."""

from dataclasses import replace
from pathlib import Path

from test_rebuild_comparisons import until

from datelier.analysis.types import Algorithm
from datelier.application.editor import EditorController
from datelier.application.workspace import capture_session
from datelier.pipeline.operations import Sort
from datelier.workspace.session_jobs import save_snapshot


def test_raw_scatter_refreshes_cluster_colors_on_fit_refit_and_clear(
    tmp_path: Path,
) -> None:
    source = tmp_path / "clusters.csv"
    source.write_text("x,y\n0.0,0.0\n0.1,0.2\n4.0,4.0\n4.1,4.2\n9.0,9.0\n9.1,9.2\n")
    original = source.read_bytes()
    editor = EditorController()
    try:
        file = editor.active
        file.open(source)
        until(editor, lambda: file.explorer.active is not None)
        file.plots.choose_color("K-means")
        file.analysis.controls.features = ["x", "y"]
        for clusters in (2, 3):
            file.analysis.controls.update(Algorithm.KMEANS, "clusters", clusters)
            file.analysis.start(Algorithm.KMEANS)
            until(
                editor,
                lambda: not file.analysis.jobs.busy and editor.workers.pending == 0,
            )
            dashboard = file.explorer.active
            assert dashboard and dashboard.scatters
            points = dashboard.scatters[0]
            assert points.colors is not None
            assert len(set(points.colors.rgba.tolist())) == clusters
            assert points.row_ids.tolist() == list(range(6))
            assert file.analysis.source is None
        file.plots.choose_color("Uniform")
        until(editor, lambda: editor.workers.pending == 0)
        dashboard = file.explorer.active
        assert dashboard and dashboard.scatters[0].colors is None
        assert source.read_bytes() == original
    finally:
        editor.close()


def test_fitted_coordinate_switch_drops_previous_result_and_never_fits_implicitly(
    tmp_path: Path,
) -> None:
    source = tmp_path / "points.csv"
    source.write_text(
        "x,y,z\n0.0,2.0,1.0\n1.0,0.0,3.0\n2.0,3.0,0.0\n3.0,1.0,2.0\n4.0,4.0,4.0\n"
    )
    original = source.read_bytes()
    editor = EditorController()
    try:
        file = editor.active
        file.open(source)
        until(
            editor,
            lambda: file.inspection is not None and file.explorer.active is not None,
        )
        file.editor.request(Sort(("x",), True))
        until(editor, lambda: not file.editor.busy and file.explorer.active is not None)
        editor.choose_relationship_chart("Scatter 3D")
        editor.poll()
        assert file.analysis.controls.dimensions == 3
        file.analysis.controls.features = list(file.plots.numeric)
        file.analysis.start(Algorithm.PCA)
        editor.choose_route("Inspect")
        until(editor, lambda: Algorithm.PCA in file.analysis.jobs.results)
        assert file.views.tab == "Inspect" and file.analysis.source is None
        file.open_analysis_result(Algorithm.PCA)
        until(editor, lambda: file.analysis.plots.active is not None)
        points = file.analysis.plots.active
        assert points and points.z is not None
        assert file.views.tab == "Relationships" and file.plots.three_d
        file.analysis.choose_source(Algorithm.UMAP)
        editor.poll()
        assert file.analysis.plots.active is None and not file.analysis.jobs.busy
        assert set(file.analysis.jobs.results) == {Algorithm.PCA}
        file.analysis.choose_source(None)
        editor.poll()
        assert file.analysis.source is None and file.explorer.active
        assert source.read_bytes() == original
        file.views = replace(file.views, scatter_height=240, scatter3d_height=350)
        save_snapshot(tmp_path / "workspace.json", capture_session(editor), False)
    finally:
        editor.close()
    reopened = EditorController()
    try:
        reopened.open_workspace(tmp_path / "workspace.json")
        until(reopened, lambda: not reopened.workspace.busy)
        file = reopened.current
        assert file.plots.three_d and file.analysis.controls.dimensions == 3
        assert file.views.scatter_height == 240 and file.views.scatter3d_height == 350
        assert not file.analysis.jobs.results and not file.analysis.jobs.busy
        file.plots.choose_color("K-means")
        editor_count = len(file.analysis.jobs.results)
        reopened.poll()
        assert (
            file.plots.cluster_result is None
            and len(file.analysis.jobs.results) == editor_count
        )
    finally:
        reopened.close()
