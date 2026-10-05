"""Fresh-process native recent opening, missing-file retry and workspace relink."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from imgui_bundle import hello_imgui, imgui

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.io.loading import LoadPhase
from datelier.io.types import CsvOptions, ImportFormat
from datelier.workspace.preferences import read_preferences
from datelier.workspace.recent import RecentKind


def run_stage(root: Path, mode: str) -> None:
    source, moved = root / "custom.csv", root / "moved.csv"
    workspace, preferences = root / "session.json", root / "preferences.json"
    stage, entered = 0, 0
    pointer, previous = (0.0, 0.0), (0.0, 0.0)
    clicking, click_frame, following = 0, 0, 0

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
        nonlocal stage, entered, pointer, clicking, click_frame, following
        io = imgui.get_io()

        def click(pixel: tuple[float, float], next_stage: int) -> None:
            nonlocal pointer, clicking, click_frame, following
            pointer = pixel
            clicking, click_frame, following = 1, evidence.frames, next_stage

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
                stage, entered = following, evidence.frames
            return
        file = editor.active
        if mode == "save":
            if stage == 0:
                editor.opening.request(
                    (source,),
                    file.identity,
                    format=ImportFormat.CSV,
                    options=CsvOptions(separator=";"),
                )
                stage = 1
            elif stage == 1 and file.loader.active is not None:
                assert file.loader.active.dataset.table.columns == ["x", "y"]
                file.workspace.path = str(workspace)
                file.workspace.save(file)
                stage = 2
            elif stage == 2 and file.workspace.jobs.saved is not None:
                assert (
                    editor.preferences.value.recent[0].source_kind
                    == RecentKind.WORKSPACE
                )
                editor.new_tab()
                stage, entered = 3, evidence.frames
            elif stage == 3 and evidence.frames > entered + 10:
                assert set(evidence.welcome_recent_pixels) == {
                    str(source),
                    str(workspace),
                }
                hello_imgui.get_runner_params().app_shall_exit = True
                stage = 10
        else:
            if stage == 0 and evidence.welcome_frames >= 10:
                assert len(editor.preferences.value.recent) == 2
                hello_imgui.get_runner_params().callbacks.post_new_frame = apply_pointer
                click(evidence.welcome_recent_pixels[str(source)], 1)
            elif stage == 1 and file.loader.status.phase == LoadPhase.FAILED:
                assert file.controls.separator == ";" and file.loader.active is None
                file.controls.path = str(moved)
                click(evidence.welcome_retry_pixel, 2)
            elif stage == 2 and file.loader.active is not None:
                assert file.loader.active.dataset.table.columns == ["x", "y"]
                assert file.loader.active.dataset.source.path == moved
                editor.close_tab(file.identity)
                stage, entered = 3, evidence.frames
            elif stage == 3 and evidence.frames > entered + 6:
                click(evidence.welcome_recent_pixels[str(workspace)], 4)
            elif stage == 4 and file.recovery is not None:
                assert file.loader.active is None
                editor.recover_source(file.identity, relink=moved)
                stage = 5
            elif stage == 5 and file.loader.active is not None:
                assert file.loader.active.dataset.table.columns == ["x", "y"]
                assert editor.workspace_jobs.opened == workspace
                assert not file.analysis.jobs.busy and not file.analysis.jobs.results
                stage, entered = 6, evidence.frames
            elif (
                stage == 6
                and evidence.frames > entered + 15
                and file.explorer.active is not None
            ):
                hello_imgui.get_runner_params().app_shall_exit = True
                stage = 10

    evidence = run_gui(
        smoke_frames=1500, preferences_path=preferences, on_editor_frame=frame
    )
    assert stage == 10, stage
    if mode == "restore":
        pixels = hello_imgui.final_app_window_screenshot()
        height, width = pixels.shape[:2]
        (root / "recent.ppm").write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
    print(
        json.dumps(
            {
                "stage": mode,
                "frames": evidence.frames,
                "native_recent_and_retry": mode == "restore",
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
    with TemporaryDirectory(prefix="datelier-recent-") as directory:
        root = Path(directory)
        source = root / "custom.csv"
        source.write_text("x;y\n1;2\n3;4\n")
        original = source.read_bytes()
        for mode in ("save", "restore"):
            subprocess.run(
                [sys.executable, __file__, "--root", str(root), "--stage", mode],
                check=True,
            )
            if mode == "save":
                assert len(read_preferences(root / "preferences.json")[0].recent) == 2
                source.rename(root / "moved.csv")
        assert (root / "moved.csv").read_bytes() == original
        Path("/tmp/datelier-recent.ppm").write_bytes((root / "recent.ppm").read_bytes())


if __name__ == "__main__":
    main()
