"""Live save/restart, missing-source recovery, history and linked-selection gate."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from imgui_bundle import hello_imgui

from datelier.editing import HistoryAction
from datelier.gui import GuiSession, InspectionEvidence, run_gui
from datelier.operations import Sort


def main() -> None:
    with TemporaryDirectory(prefix="datelier-workspace-") as folder:
        root = Path(folder)
        source, workspace = root / "data.csv", root / "session.datelier"
        source.write_text("x,y,z,group\n3,9,1,a\n1,5,2,b\n2,7,3,a\n4,2,4,b\n")
        before = source.read_bytes()
        stage = 0
        ready = 0

        def save_frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, ready
            active = session.loader.active
            if active is None:
                return
            if stage == 0:
                session.editor.request(Sort(("x",)))
                stage = 1
            elif stage == 1 and not session.editor.busy:
                session.editor.request(HistoryAction.UNDO)
                stage = 2
            elif stage == 2 and not session.editor.busy:
                session.plots.custom_scatter = True
                session.plots.x_index, session.plots.y_index = 1, 0
                session.plots.compare_columns = ["x", "y"]
                session.plots.color_index = (
                    session.plots.color_columns.index("group") + 1
                )
                session.plots.bins = 7
                session.analysis.controls.features = ["y", "x", "z"]
                session.analysis.controls.seed = 17
                session.analysis.controls.clusters = 2
                session.analysis.controls.pca_whiten = True
                session.exploration.tab = "Correlations"
                session.exploration.relationships.mode = 1
                session.exploration.profile_mode = 2
                session.explorer.request(active.dataset, session.plots.settings())
                ready, stage = evidence.frames, 3
            elif (
                stage == 3
                and evidence.frames > ready + 15
                and not session.explorer.busy
            ):
                session.workspace.path = str(workspace)
                session.workspace.save(session)
                stage = 4
            elif stage == 4 and not session.workspace.jobs.busy:
                assert session.workspace.jobs.saved is not None, (
                    session.workspace.jobs.message
                )
                session.workspace.path = str(root / "missing.datelier")
                session.workspace.open(session)
                ready, stage = evidence.frames, 5
            elif stage == 5 and not session.workspace.jobs.busy:
                assert "failed" in session.workspace.jobs.message.lower()
                assert (
                    session.editor.pipeline is not None
                    and session.editor.pipeline.cursor == 0
                )
                assert active.dataset.table["x"].to_list() == [3, 1, 2, 4]
                if evidence.frames > ready + 10:
                    hello_imgui.get_runner_params().app_shall_exit = True

        first = run_gui(source, smoke_frames=2000, on_frame=save_frame)
        assert stage == 5 and workspace.exists()
        moved = root / "moved.csv"
        source.rename(moved)
        stage, ready = 0, 0
        selected = False

        def reopen_frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, ready, selected
            jobs = session.workspace.jobs
            if stage == 0 and jobs.issue is not None:
                hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                    "Workspace"
                )
                ready, stage = evidence.frames, 1
            elif stage == 1 and evidence.frames > ready + 15:
                session.workspace.relink_path = str(moved)
                session.workspace.open(session, relink=True)
                stage = 2
            active = session.loader.active
            if active is None:
                return
            assert not session.analysis.jobs.busy and not session.analysis.jobs.results
            if stage == 2 and not session.explorer.busy:
                pipeline = session.editor.pipeline
                assert (
                    pipeline is not None and pipeline.can_redo and pipeline.cursor == 0
                )
                assert active.dataset.source.path == moved
                assert session.plots.bins == 7 and session.plots.compare_columns == [
                    "x",
                    "y",
                ]
                assert (
                    session.analysis.controls.seed == 17
                    and session.analysis.controls.pca_whiten
                )
                assert session.analysis.controls.features == ["y", "x", "z"]
                assert session.exploration.relationships.mode == 1
                assert session.exploration.active_tab == "Correlations"
                assert session.exploration.profile_mode == 2
                session.editor.request(HistoryAction.REDO)
                stage = 3
            elif stage == 3 and not session.editor.busy and not session.explorer.busy:
                assert active.dataset.row_ids.to_list() == [1, 2, 0, 3]
                session.exploration.tab = "Scatter"
                session.selection.choose(active.dataset.revision, (1,))
                ready, stage = evidence.frames, 4
            elif stage == 4 and evidence.frames > ready + 20:
                assert session.exploration.interaction.selected_points == 1
                selected = True
                hello_imgui.get_runner_params().app_shall_exit = True

        second = run_gui(
            initial_workspace=workspace, smoke_frames=2000, on_frame=reopen_frame
        )
        assert stage == 4 and selected
        assert moved.read_bytes() == before
        pixels = hello_imgui.final_app_window_screenshot()
        height, width = pixels.shape[:2]
        Path("/tmp/datelier-workspace.ppm").write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        print(
            json.dumps(
                {
                    "save_frames": first.frames,
                    "restore_frames": second.frames,
                    "missing_source_relinked": True,
                    "redo_and_selection": True,
                    "implicit_ml_runs": 0,
                    "profile_chart_type_restored": True,
                    "source_preserved": True,
                }
            )
        )


if __name__ == "__main__":
    main()
