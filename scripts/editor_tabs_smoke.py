"""Native two-file tab input, independent jobs, history and docking smoke."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from imgui_bundle import hello_imgui, imgui

from datelier.analysis.types import Algorithm
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.file_session import FileSession
from datelier.gui.tabs import EditorTabs
from datelier.pipeline.operations import Sort


def main() -> None:
    mouse_target: tuple[float, float] | None = None
    mouse_previous: tuple[float, float] | None = None

    def apply_pointer() -> None:
        nonlocal mouse_previous
        if mouse_target is None:
            return
        io = imgui.get_io()
        previous = mouse_previous or mouse_target
        io.mouse_pos = imgui.ImVec2(*mouse_target)
        io.mouse_delta = imgui.ImVec2(
            mouse_target[0] - previous[0], mouse_target[1] - previous[1]
        )
        io.want_set_mouse_pos = True
        mouse_previous = mouse_target

    stage, entered = 0, 0
    drag_start, drag_end = (0.0, 0.0), (0.0, 0.0)
    first: FileSession | None = None
    second: FileSession | None = None
    observations: dict[str, bool | int] = {}
    with TemporaryDirectory(prefix="datelier-tabs-") as directory:
        root = Path(directory)
        train, test = root / "train.csv", root / "test.csv"
        train.write_text("x,y,group\n3,6,a\n1,2,b\n2,4,a\n4,8,b\n")
        test.write_text("x,y,group\n30,60,b\n10,20,a\n20,40,b\n40,80,a\n")
        originals = (train.read_bytes(), test.read_bytes())

        def frame(
            editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, first, second, drag_start, drag_end
            nonlocal mouse_target
            age = evidence.frames - entered
            io = imgui.get_io()

            def move(pixel: tuple[float, float]) -> None:
                nonlocal mouse_target
                mouse_target = pixel

            if stage == 0 and editor.active.explorer.active is not None:
                hello_imgui.get_runner_params().callbacks.post_new_frame = apply_pointer
                first = editor.active
                first.plots.bins = 7
                first.analysis.controls.seed = 9
                first.editor.request(Sort(("x",)))
                second = editor.new_tab(test)
                stage = 1
            elif stage == 1:
                assert first is not None and second is not None
                if second.explorer.active is None or first.editor.busy:
                    return
                assert second.loader.active is not None
                assert first.loader.active is not None
                first.selection.choose(first.loader.active.dataset.revision, [1])
                second.selection.choose(second.loader.active.dataset.revision, [2])
                second.plots.bins = 13
                second.analysis.controls.seed = 19
                first.analysis.controls.features = ["x", "y"]
                first.analysis.controls.start(
                    first.analysis.jobs, first.loader.active.dataset, Algorithm.PCA
                )
                assert first.analysis.jobs.busy
                assert editor.active is second
                stage, entered = 2, evidence.frames
            elif stage == 2:
                assert first is not None and second is not None
                assert editor.active is second
                assert (
                    not second.analysis.jobs.busy and not second.analysis.jobs.results
                )
                if first.analysis.jobs.busy:
                    observations["inactive_analysis_running"] = True
                    return
                assert Algorithm.PCA in first.analysis.jobs.results
                assert first.selection.row_ids == {1} and second.selection.row_ids == {
                    2
                }
                assert first.editor.pipeline is not None
                assert first.editor.pipeline.can_undo
                assert second.editor.pipeline is not None
                assert not second.editor.pipeline.can_undo
                move(tabs.pixels[first.identity])
                stage, entered = 3, evidence.frames
            elif stage == 3:
                assert first is not None
                move(tabs.pixels[first.identity])
                if age <= 4:
                    return

                io.add_mouse_button_event(0, True)
                stage, entered = 4, evidence.frames
            elif stage == 4 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 5, evidence.frames
            elif stage == 5 and age > 10:
                assert first is not None and second is not None
                assert editor.active is first
                assert first.loader.active is not None
                assert first.loader.active.dataset.row_ids.to_list() == [1, 2, 0, 3]
                assert first.table.selected_visible_rows == 1
                assert (first.plots.bins, second.plots.bins) == (7, 13)
                assert (
                    first.analysis.controls.seed,
                    second.analysis.controls.seed,
                ) == (9, 19)
                assert evidence.table_dock_id and evidence.schema_dock_id
                observations["native_switch_history_selection_controls"] = True
                drag_start = tabs.pixels[first.identity]
                x, y = tabs.pixels[second.identity]
                drag_end = (x + 10, y)
                move(drag_start)
                stage, entered = 6, evidence.frames
            elif stage == 6 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 7, evidence.frames
            elif stage == 7:
                assert first is not None and second is not None
                x1, y = drag_start
                x2, _ = drag_end
                move((x1 + (x2 - x1) * min(age / 12, 1), y))
                if age > 12:
                    stage, entered = 8, evidence.frames
            elif stage == 8 and age > 8:
                io.add_mouse_button_event(0, False)
                stage, entered = 9, evidence.frames
            elif stage == 9 and age > 10:
                assert first is not None and second is not None
                assert editor.files == [second, first], [
                    f.controls.path for f in editor.files
                ]
                observations["native_drag_reorder"] = True
                move(tabs.pixels[first.identity])
                stage, entered = 10, evidence.frames
            elif stage == 10 and age > 3:
                io.add_mouse_button_event(2, True)
                stage, entered = 11, evidence.frames
            elif stage == 11 and age > 3:
                io.add_mouse_button_event(2, False)
                stage, entered = 12, evidence.frames
            elif stage == 12 and age > 10:
                assert first is not None and second is not None
                assert first.closed and editor.files == [second]
                assert editor.active is second
                assert second.selection.row_ids == {2}
                observations["native_close_retains_sibling"] = True
                move(tabs.new_pixel)
                stage, entered = 13, evidence.frames
            elif stage == 13 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 14, evidence.frames
            elif stage == 14 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 15, evidence.frames
            elif stage == 15 and age > 10:
                assert second is not None
                assert len(editor.files) == 2 and editor.active is not second
                assert editor.active.loader.active is None
                observations["native_new_tab"] = True
                editor.activate(second.identity)
                stage, entered = 16, evidence.frames
            elif stage == 16 and age > 10:
                assert second is not None and editor.active is second
                assert second.table.selected_visible_rows == 1
                observations["dockable_panels_active_file"] = True
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(train, smoke_frames=3000, on_editor_frame=frame)
        assert (train.read_bytes(), test.read_bytes()) == originals
        observations["source_preserved"] = True
        observations["frames"] = evidence.frames
        pixels = hello_imgui.final_app_window_screenshot()
        height, width = pixels.shape[:2]
        Path("/tmp/datelier-editor-tabs.ppm").write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        print(json.dumps(observations))
        assert stage == 16, (stage, observations)


if __name__ == "__main__":
    main()
