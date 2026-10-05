"""Live dock rearrangement/restart/reset and theme/plot preference acceptance."""

import json
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory

from imgui_bundle import hello_imgui, imgui

from datelier.gui.app import GuiSession, InspectionEvidence, run_gui
from datelier.pipeline.operations import Sort
from datelier.workspace.preferences import Theme, read_preferences


def main() -> None:
    if len(sys.argv) == 1:
        with TemporaryDirectory(prefix="datelier-preferences-") as folder:
            for mode in ("save", "defaults", "reopen"):
                result = subprocess.run(
                    [sys.executable, __file__, mode, folder],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
                if result.returncode:
                    raise RuntimeError(result.stderr)
                if result.stdout.strip():
                    print(result.stdout.strip())
        return
    mode = sys.argv[1]
    with nullcontext(sys.argv[2]) as folder:
        root = Path(folder)
        source, workspace, preferences = (
            root / "data.csv",
            root / "session.datelier",
            root / "preferences.json",
        )
        if mode == "save":
            source.write_text("x,y\n3,4\n1,2\n2,3\n")
        before = source.read_bytes()
        stage = ready = 0
        moved_dock = 0

        def save_frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, ready, moved_dock
            active = session.loader.active
            if active is None:
                return
            params = hello_imgui.get_runner_params()
            if stage == 0:
                session.editor.request(Sort(("x",)))
                stage = 1
            elif stage == 1 and not session.editor.busy and not session.explorer.busy:
                session.plots.bins = 7
                session.workspace.path = str(workspace)
                session.workspace.save(session)
                stage = 2
            elif stage == 2 and not session.workspace.jobs.busy:
                assert session.workspace.jobs.saved is not None
                session.preferences.apply_theme(Theme.LIGHT)
                session.plots.bins = 9
                session.plots.compare_columns = ["y", "x"]
                session.exploration.tab = "Scatter"
                session.explorer.request(active.dataset, session.plots.settings())
                moved_dock = evidence.schema_dock_id
                assert moved_dock != evidence.table_dock_id and moved_dock != 0
                imgui.internal.dock_builder_dock_window("Table preview", moved_dock)
                params.docking_params.focus_dockable_window("Table preview")
                for window in params.docking_params.dockable_windows:
                    if window.label == "Analysis":
                        window.is_visible = False
                ready, stage = evidence.frames, 3
            elif stage == 3 and evidence.frames > ready + 15:
                assert evidence.table_dock_id == moved_dock, (
                    evidence.table_dock_id,
                    moved_dock,
                )
                hello_imgui.get_runner_params().app_shall_exit = True

        if mode == "save":
            first = run_gui(
                source,
                preferences_path=preferences,
                smoke_frames=2000,
                on_frame=save_frame,
            )
            assert stage == 3
            (root / "evidence.json").write_text(
                json.dumps(
                    {
                        "save_frames": first.frames,
                        "moved_dock": moved_dock,
                    }
                )
            )
            return
        previous = json.loads((root / "evidence.json").read_text())
        moved_dock = previous["moved_dock"]
        saved, message = read_preferences(preferences)
        assert saved.theme == Theme.LIGHT and saved.plots.bins == 9, message
        assert saved.plots.comparison.columns == ("y", "x")
        assert "Analysis" in saved.hidden_windows and saved.layout
        if mode == "defaults":

            def defaults_frame(
                session: GuiSession, evidence: InspectionEvidence
            ) -> None:
                if evidence.frames < 10:
                    hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                        "Table preview"
                    )
                if (
                    session.loader.active is None
                    or session.explorer.busy
                    or evidence.frames < 15
                ):
                    return
                assert session.plots.bins == 9
                assert session.plots.compare_columns == ["y", "x"]
                assert session.exploration.active_tab == "Relationships"
                assert session.preferences.value.theme == Theme.LIGHT
                assert evidence.table_dock_id == moved_dock, (
                    evidence.table_dock_id,
                    moved_dock,
                )
                hello_imgui.get_runner_params().app_shall_exit = True

            defaults = run_gui(
                source,
                preferences_path=preferences,
                smoke_frames=2000,
                on_frame=defaults_frame,
            )
            assert defaults.frames < 2000
            pixels = hello_imgui.final_app_window_screenshot()
            height, width = pixels.shape[:2]
            Path("/tmp/datelier-preferences-light.ppm").write_bytes(
                f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
            )
            print(json.dumps({"default_plot_restore_frames": defaults.frames}))
            return
        stage = ready = 0
        reset_revision = None

        def reopen_frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, ready, reset_revision
            active = session.loader.active
            if active is None or session.explorer.busy:
                return
            params = hello_imgui.get_runner_params()
            pipeline = session.editor.pipeline
            assert pipeline is not None and pipeline.cursor == 1
            if stage == 0:
                assert evidence.table_dock_id == moved_dock, (
                    evidence.table_dock_id,
                    moved_dock,
                )
                assert session.preferences.value.theme == Theme.LIGHT
                assert imgui.get_style().color_(imgui.Col_.window_bg).x > 0.8
                assert (
                    session.plots.bins == 7
                )  # workspace overrides global plot defaults
                assert active.dataset.row_ids.to_list() == [1, 2, 0]
                assert (
                    not session.analysis.jobs.busy and not session.analysis.jobs.results
                )
                reset_revision = active.dataset.revision
                session.preferences.reset_requested = True
                ready, stage = evidence.frames, 1
            elif stage == 1 and evidence.frames > ready + 10:
                assert evidence.table_dock_id != moved_dock
                assert active.dataset.revision == reset_revision
                assert all(w.is_visible for w in params.docking_params.dockable_windows)
                session.preferences.restore_layout()
                ready, stage = evidence.frames, 2
            elif stage == 2 and evidence.frames > ready + 10:
                params.docking_params.focus_dockable_window("Table preview")
                ready, stage = evidence.frames, 3
            elif stage == 3 and evidence.frames > ready + 10:
                assert evidence.table_dock_id == moved_dock, (
                    evidence.table_dock_id,
                    moved_dock,
                )
                assert active.dataset.revision == reset_revision
                assert not params.docking_params.dockable_window_of_name(
                    "Analysis"
                ).is_visible
                session.preferences.reset_requested = True
                ready, stage = evidence.frames, 4
            elif stage == 4 and evidence.frames > ready + 10:
                assert evidence.table_dock_id != moved_dock
                assert active.dataset.revision == reset_revision
                session.preferences.apply_theme(Theme.CLASSIC)
                session.selection.choose(active.dataset.revision, (1,))
                session.exploration.tab = "Scatter"
                ready, stage = evidence.frames, 5
            elif stage == 5 and evidence.frames > ready + 20:
                assert session.exploration.interaction.selected_points == 1
                assert session.table.selected_visible_rows == 1
                hello_imgui.get_runner_params().app_shall_exit = True

        second = run_gui(
            initial_workspace=workspace,
            preferences_path=preferences,
            smoke_frames=2000,
            on_frame=reopen_frame,
        )
        assert stage == 5
        final, message = read_preferences(preferences)
        assert final.theme == Theme.CLASSIC and not final.hidden_windows, message
        assert source.read_bytes() == before
        pixels = hello_imgui.final_app_window_screenshot()
        height, width = pixels.shape[:2]
        Path("/tmp/datelier-preferences.ppm").write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        print(
            json.dumps(
                {
                    "save_frames": previous["save_frames"],
                    "reopen_frames": second.frames,
                    "moved_dock": moved_dock,
                    "layout_restored_and_reset": True,
                    "themes": ["Light", "Classic"],
                    "plot_defaults": 9,
                    "workspace_bins": 7,
                    "linked_selection": True,
                    "recipe_preserved": True,
                    "source_preserved": True,
                }
            )
        )


if __name__ == "__main__":
    main()
