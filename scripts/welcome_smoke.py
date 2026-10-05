"""Native Welcome, multiple file selection and folder opening smoke."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from imgui_bundle import hello_imgui, imgui

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", choices=("welcome", "picker"))
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-welcome.ppm")
    )
    args = parser.parse_args()
    stage, entered = 0, 0
    pointer = (0.0, 0.0)
    previous = pointer
    clicking, click_frame, next_stage = 0, 0, 0
    blank_id = ""
    revisions: dict[Path, object] = {}

    def apply_pointer() -> None:
        nonlocal previous
        io = imgui.get_io()
        io.mouse_pos = imgui.ImVec2(*pointer)
        io.mouse_delta = imgui.ImVec2(
            pointer[0] - previous[0], pointer[1] - previous[1]
        )
        io.want_set_mouse_pos = True
        previous = pointer

    with TemporaryDirectory(prefix="datelier-welcome-") as directory:
        root = Path(directory)
        train, test = root / "train.csv", root / "test.csv"
        train.write_text("x,y\n1,2\n3,4\n")
        test.write_text("x,y\n10,20\n30,40\n")
        (root / "ignored.txt").write_text("not a table")
        originals = (train.read_bytes(), test.read_bytes())

        def frame(
            editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, pointer, clicking, click_frame, next_stage
            nonlocal blank_id, revisions
            io = imgui.get_io()

            def click(pixel: tuple[float, float], following: int) -> None:
                nonlocal pointer, clicking, click_frame, next_stage
                pointer = pixel
                clicking, click_frame, next_stage = 1, evidence.frames, following

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
                    stage, entered = next_stage, evidence.frames
                return
            if stage == 0 and evidence.welcome_frames >= 10:
                assert editor.active.loader.active is None
                if args.capture == "welcome":
                    hello_imgui.get_runner_params().app_shall_exit = True
                    stage = 10
                    return
                hello_imgui.get_runner_params().callbacks.post_new_frame = apply_pointer
                editor.browser.path = str(root)
                click(evidence.welcome_open_files_pixel, 1)
            elif stage == 1:
                browser = editor.browser
                if (
                    browser.listing is None
                    or browser.busy
                    or len(browser.row_pixels) < 2
                ):
                    return
                assert browser.visible and len(browser.listing.files) == 2
                if args.capture == "picker":
                    hello_imgui.get_runner_params().app_shall_exit = True
                    stage = 10
                    return
                click(browser.row_pixels[train], 2)
            elif stage == 2:
                assert editor.browser.selected == {train}
                click(editor.browser.row_pixels[test], 3)
            elif stage == 3:
                assert editor.browser.selected == {train, test}
                click(editor.browser.open_pixel, 4)
            elif stage == 4:
                if (
                    editor.opening.busy
                    or len(editor.files) != 2
                    or any(file.loader.active is None for file in editor.files)
                ):
                    return
                revisions = {
                    file.loader.active.dataset.source.path: file.loader.revision
                    for file in editor.files
                    if file.loader.active is not None
                }
                assert set(revisions) == {train, test}
                editor.opening.request((train,), editor.active.identity)
                stage = 5
            elif stage == 5:
                if editor.opening.busy:
                    return
                assert editor.active.loader.active is not None
                assert editor.active.loader.active.dataset.source.path == train
                assert len(editor.files) == 2
                blank_id = editor.new_tab().identity
                stage, entered = 6, evidence.frames
            elif stage == 6 and evidence.frames > entered + 5:
                assert editor.active.identity == blank_id
                click(evidence.welcome_open_folder_pixel, 7)
            elif stage == 7:
                if editor.browser.busy or editor.browser.listing is None:
                    return
                assert editor.browser.visible and editor.browser.folder_mode
                assert len(editor.browser.listing.files) == 2
                click(editor.browser.all_pixel, 8)
            elif stage == 8:
                if editor.opening.busy:
                    return
                assert len(editor.files) == 3
                for file in editor.files:
                    if file.loader.active is not None:
                        assert (
                            file.loader.revision
                            == revisions[file.loader.active.dataset.source.path]
                        )
                    assert (
                        not file.analysis.jobs.busy and not file.analysis.jobs.results
                    )
                editor.close_tab(blank_id)
                stage, entered = 9, evidence.frames
            elif stage == 9 and evidence.frames > entered + 10:
                assert len(editor.files) == 2
                hello_imgui.get_runner_params().app_shall_exit = True
                stage = 10

        evidence = run_gui(smoke_frames=2000, on_editor_frame=frame)
        assert (train.read_bytes(), test.read_bytes()) == originals
        pixels = hello_imgui.final_app_window_screenshot()
        height, width = pixels.shape[:2]
        args.output.write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        assert stage == 10, stage
        print(
            json.dumps(
                {
                    "frames": evidence.frames,
                    "welcome_frames": evidence.welcome_frames,
                    "native_multi_select": args.capture is None,
                    "native_folder_open": args.capture is None,
                    "duplicate_focus_without_reload": args.capture is None,
                    "source_preserved": True,
                    "implicit_ml_runs": 0,
                }
            )
        )


if __name__ == "__main__":
    main()
