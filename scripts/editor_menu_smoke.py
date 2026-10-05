"""Native editor menus, contextual import/workspace actions and layout recovery."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from imgui_bundle import hello_imgui, imgui

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.workspace.preferences import Preferences, Theme, save_preferences


def main() -> None:
    stage, entered = 0, 0
    pointer, previous = (0.0, 0.0), (0.0, 0.0)
    clicking, click_frame, following = 0, 0, 0
    restored_revision: object = None

    def apply_pointer() -> None:
        nonlocal previous
        io = imgui.get_io()
        io.mouse_pos = imgui.ImVec2(*pointer)
        io.mouse_delta = imgui.ImVec2(
            pointer[0] - previous[0], pointer[1] - previous[1]
        )
        io.want_set_mouse_pos = True
        previous = pointer

    with TemporaryDirectory(prefix="datelier-editor-menu-") as directory:
        root = Path(directory)
        source, workspace, preferences = (
            root / "custom.csv",
            root / "session.json",
            root / "preferences.json",
        )
        source.write_text("x;y\n1;2\n3;4\n")
        original = source.read_bytes()
        old_layout = (
            "[Window][Table preview]\n[Window][Open dataset]\n"
            "[Docking][Data]\nDockSpace ID=1\n"
        )
        save_preferences(preferences, Preferences(theme=Theme.LIGHT, layout=old_layout))

        def frame(
            editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
        ) -> None:
            nonlocal \
                stage, \
                entered, \
                pointer, \
                clicking, \
                click_frame, \
                following, \
                restored_revision
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
            menus, actions = evidence.menu_pixels, evidence.dialog_pixels
            windows = hello_imgui.get_runner_params().docking_params.dockable_windows
            if stage == 0 and evidence.welcome_frames >= 10:
                assert "layout reset" in editor.preferences.message
                assert editor.preferences.value.theme == Theme.LIGHT
                labels = {window.label for window in windows}
                assert not labels.intersection(("Open dataset", "Workspace"))
                hello_imgui.get_runner_params().callbacks.post_new_frame = apply_pointer
                click(menus["File"], 1)
            elif stage == 1:
                click(menus["Import settings…"], 2)
            elif stage == 2:
                file.controls.path, file.controls.separator = str(source), ";"
                stage, entered = 21, evidence.frames
            elif stage == 21 and evidence.frames > entered + 4:
                click(actions["Import"], 3)
            elif stage == 3 and file.loader.active is not None:
                assert file.loader.active.dataset.table.columns == ["x", "y"]
                click(actions["Close dialog"], 4)
            elif stage == 4:
                click(menus["File"], 5)
            elif stage == 5:
                click(menus["Workspace actions…"], 6)
            elif stage == 6:
                editor.workspace_path = str(workspace)
                click(actions["Save workspace"], 7)
            elif stage == 7 and editor.workspace_jobs.saved is not None:
                click(actions["Close dialog"], 8)
            elif stage == 8:
                click(menus["File"], 9)
            elif stage == 9:
                click(menus["New Tab"], 10)
            elif stage == 10:
                assert file.loader.active is None
                click(menus["File"], 11)
            elif stage == 11:
                click(menus["Workspace actions…"], 12)
            elif stage == 12:
                editor.workspace_path = str(workspace)
                click(actions["Open workspace"], 13)
            elif stage == 13 and file.loader.active is not None:
                assert file.loader.active.dataset.table.columns == ["x", "y"]
                assert len(editor.files) == 1
                restored_revision = file.loader.revision
                click(actions["Close dialog"], 14)
            elif stage == 14:
                click(menus["Preferences"], 15)
            elif stage == 15:
                click(menus["Reset layout"], 16)
            elif (
                stage == 16
                and evidence.frames > entered + 12
                and not file.explorer.busy
            ):
                assert file.loader.revision == restored_revision
                assert editor.preferences.message == "Default layout restored."
                assert all(window.is_visible for window in windows)
                assert not file.analysis.jobs.busy and not file.analysis.jobs.results
                hello_imgui.get_runner_params().app_shall_exit = True
                stage = 17

        evidence = run_gui(
            smoke_frames=2000, preferences_path=preferences, on_editor_frame=frame
        )
        assert stage == 17, stage
        assert source.read_bytes() == original and workspace.exists()
        pixels = hello_imgui.final_app_window_screenshot()
        height, width = pixels.shape[:2]
        Path("/tmp/datelier-editor-menu.ppm").write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        print(
            json.dumps(
                {
                    "frames": evidence.frames,
                    "native_menu_import_save_reopen": True,
                    "old_layout_recovered": True,
                    "native_reset_layout": True,
                    "source_preserved": True,
                    "implicit_ml_runs": 0,
                }
            )
        )


if __name__ == "__main__":
    main()
