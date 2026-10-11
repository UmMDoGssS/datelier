"""Prepared pair modes, original identities, empty choices and saved matrix views."""

from dataclasses import replace
from pathlib import Path

from test_rebuild_comparisons import until

from datelier.application.sessions import EditorController
from datelier.application.sessions.workspace import capture_session
from datelier.pipeline.operations import Sort
from datelier.workspace.sessions.jobs import save_snapshot


def test_sorted_pair_identity_and_all_diagonals_reopen_without_analysis(
    tmp_path: Path,
) -> None:
    source = tmp_path / "matrix.csv"
    source.write_text(
        "x,y,z\n0.0,2.0,1.0\n1.0,0.0,3.0\n2.0,3.0,0.0\n3.0,1.0,2.0\n4.0,4.0,4.0\n"
    )
    original = source.read_bytes()
    workspace = tmp_path / "workspace.json"
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
        file.plots.relationship_features = ["x", "y", "z"]
        file.views = replace(file.views, relationship_mode=1, relationship_height=380)
        for mode in range(5):
            file.plots.diagonal_mode = mode
            until(
                editor,
                lambda mode=mode: (
                    file.explorer.active is not None
                    and file.explorer.active.relationships is not None
                    and file.explorer.active.relationships.diagonal_mode == mode
                ),
            )
            data = file.explorer.active.relationships if file.explorer.active else None
            assert data
            points = data.cells[0][1]
            assert points
            assert points.x_name == "y" and points.y_name == "x"
            assert points.row_ids.tolist() == [4, 3, 2, 1, 0]
            assert points.positions.tolist() == [0, 1, 2, 3, 4]
            if mode:
                assert all(
                    d and d.series[0].count == 5 for d in data.diagonal_distributions
                )
            assert not file.analysis.jobs.results
        editor.choose_route("Correlations")
        save_snapshot(workspace, capture_session(editor), False)
        file.plots.relationship_features = []
        editor.poll()
        assert file.plots.relationship_features == []
        assert source.read_bytes() == original
    finally:
        editor.close()
    reopened = EditorController()
    try:
        reopened.open_workspace(workspace)
        until(
            reopened,
            lambda: (
                not reopened.workspace.busy
                and reopened.current.explorer.active is not None
            ),
        )
        file = reopened.current
        assert file.views.tab == "Correlations" and file.views.relationship_mode == 1
        assert file.views.relationship_height == 380 and file.plots.diagonal_mode == 4
        assert (
            file.plots.relationship_features == ["x", "y", "z"]
            and not file.analysis.jobs.results
        )
    finally:
        reopened.close()
