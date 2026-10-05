"""Fresh-process session API save/reopen and independent native tab recovery."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from imgui_bundle import hello_imgui, imgui

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.pipeline.operations import Sort
from datelier.workspace.session_storage import read_session_workspace


def run_stage(root: Path, mode: str) -> None:
    source, test, workspace = (
        root / "train.csv",
        root / "test.csv",
        root / "session.datelier",
    )
    stage, entered = 0, 0
    expected_dock = (
        int(json.loads((root / "layout-evidence.json").read_text())["table_dock"])
        if mode == "restore"
        else 0
    )
    recovered_revision: object = None
    pointer, previous = (0.0, 0.0), (0.0, 0.0)
    clicking, click_frame = 0, 0

    def apply_pointer() -> None:
        nonlocal previous
        io = imgui.get_io()
        io.mouse_pos = imgui.ImVec2(*pointer)
        io.mouse_delta = imgui.ImVec2(
            pointer[0] - previous[0], pointer[1] - previous[1]
        )
        io.want_set_mouse_pos = True
        previous = pointer

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered, recovered_revision, pointer, clicking, click_frame
        io = imgui.get_io()
        if clicking:
            age = evidence.frames - click_frame
            if clicking == 1 and age > 3:
                io.add_mouse_button_event(0, True)
                clicking, click_frame = 2, evidence.frames
            elif clicking == 2 and age > 3:
                io.add_mouse_button_event(0, False)
                clicking, click_frame = 3, evidence.frames
            elif clicking == 3 and age > 6:
                clicking = 0
                stage = 2
            return
        if mode == "save":
            if stage == 0:
                editor.opening.request((source, test), editor.active_id)
                stage = 1
            elif (
                stage == 1
                and len(editor.files) == 2
                and all(file.loader.active is not None for file in editor.files)
            ):
                editor.files[0].editor.request(Sort(("x",)))
                stage = 2
            elif stage == 2 and not editor.files[0].editor.busy:
                train, other = editor.files
                train.plots.bins, other.plots.bins = 7, 13
                train.analysis.controls.seed, other.analysis.controls.seed = 17, 29
                assert train.loader.revision is not None
                train.selection.choose(train.loader.revision, (1,))
                blank = editor.new_tab()
                editor.reorder((other.identity, blank.identity, train.identity))
                editor.activate(train.identity)
                params = hello_imgui.get_runner_params()
                imgui.internal.dock_builder_dock_window(
                    "Table preview", evidence.schema_dock_id
                )
                params.docking_params.focus_dockable_window("Table preview")
                params.docking_params.dockable_window_of_name(
                    "Analysis"
                ).is_visible = False
                stage, entered = 3, evidence.frames
            elif stage == 3 and evidence.frames > entered + 8:
                assert tabs.native_order == tuple(
                    file.identity for file in editor.files
                )
                assert evidence.table_dock_id == evidence.schema_dock_id
                editor.save_workspace(
                    workspace,
                    layout=imgui.save_ini_settings_to_memory(),
                    hidden=("Analysis",),
                )
                stage = 4
            elif stage == 4 and editor.workspace_jobs.saved is not None:
                hello_imgui.get_runner_params().app_shall_exit = True
                stage = 10
        else:
            if stage == 0:
                stage = 1
            elif (
                stage == 1 and not editor.workspace_jobs.busy and len(editor.files) == 3
            ):
                good, blank, failed = editor.files
                assert good.loader.active is not None and blank.loader.active is None
                assert failed.recovery is not None and editor.active is failed
                assert good.plots.bins == 13 and good.analysis.controls.seed == 29
                recovered_revision = good.loader.revision
                if (
                    hello_imgui.get_runner_params()
                    .docking_params.dockable_window_of_name("Analysis")
                    .is_visible
                ):
                    return
                failed.workspace.relink_path = str(root / "moved.csv")
                hello_imgui.get_runner_params().callbacks.post_new_frame = apply_pointer
                stage, entered = 11, evidence.frames
            elif stage == 11 and evidence.frames > entered + 5:
                assert evidence.welcome_recovery_pixel != (0, 0)
                pointer = evidence.welcome_recovery_pixel
                clicking, click_frame = 1, evidence.frames
            elif stage == 2 and not editor.workspace_jobs.busy:
                good, _, train = editor.files
                assert train.loader.active is not None and train.recovery is None
                assert train.plots.bins == 7 and train.analysis.controls.seed == 17
                assert train.selection.row_ids == {1}
                assert train.loader.active.dataset.row_ids.to_list() == [1, 2, 0]
                assert good.loader.revision == recovered_revision
                stage, entered = 3, evidence.frames
            elif (
                stage == 3
                and evidence.frames > entered + 20
                and not editor.active.explorer.busy
            ):
                assert tabs.native_order == tuple(
                    file.identity for file in editor.files
                )
                assert evidence.table_dock_id == expected_dock, (
                    evidence.table_dock_id,
                    expected_dock,
                    evidence.schema_dock_id,
                )
                assert editor.active is editor.files[2]
                assert editor.active.table.selected_visible_rows == 1
                assert all(
                    not file.analysis.jobs.busy and not file.analysis.jobs.results
                    for file in editor.files
                )
                hello_imgui.get_runner_params().app_shall_exit = True
                stage = 10

    evidence = run_gui(
        smoke_frames=1500,
        on_editor_frame=frame,
        initial_workspace=workspace if mode == "restore" else None,
    )
    assert stage == 10, stage
    if mode == "save":
        (root / "layout-evidence.json").write_text(
            json.dumps({"table_dock": evidence.table_dock_id})
        )
    if mode == "restore":
        pixels = hello_imgui.final_app_window_screenshot()
        height, width = pixels.shape[:2]
        Path("/tmp/datelier-session-workspace.ppm").write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
    print(
        json.dumps(
            {
                "stage": mode,
                "pid": os.getpid(),
                "frames": evidence.frames,
                "whole_session_api": True,
                "native_tab_order": True,
                "implicit_ml_runs": 0,
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--stage", choices=("save", "restore"))
    args = parser.parse_args()
    if args.root is not None and args.stage is not None:
        run_stage(args.root, args.stage)
        return
    with TemporaryDirectory(prefix="datelier-session-") as directory:
        root = Path(directory)
        source, test = root / "train.csv", root / "test.csv"
        source.write_text("x,y\n3,6\n1,2\n2,4\n")
        test.write_text("a,b\n10,20\n30,40\n")
        originals = source.read_bytes(), test.read_bytes()
        subprocess.run(
            [sys.executable, __file__, "--root", str(root), "--stage", "save"],
            check=True,
        )
        saved = read_session_workspace(root / "session.datelier")
        assert len(saved.files) == 3 and saved.files[1].recipe is None
        source.rename(root / "moved.csv")
        subprocess.run(
            [sys.executable, __file__, "--root", str(root), "--stage", "restore"],
            check=True,
        )
        assert ((root / "moved.csv").read_bytes(), test.read_bytes()) == originals


if __name__ == "__main__":
    main()
