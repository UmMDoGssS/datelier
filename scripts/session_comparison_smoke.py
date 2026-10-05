"""Native comparison controls, diagnostics and fresh-process restoration."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from imgui_bundle import hello_imgui, imgui

from datelier.core.column_roles import ColumnRole
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.inspection.comparison_settings import (
    ComparisonSettings,
    ComparisonSource,
    Normalization,
)
from datelier.pipeline.operations import SetColumnRole
from datelier.workspace.session_storage import read_session_workspace


def stage_run(root: Path, mode: str) -> None:
    stage, entered, next_stage = 0, 0, 0
    click, click_frame = 0, 0
    pointer, previous = (0.0, 0.0), (0.0, 0.0)
    initial_started = 0
    workspace = root / "session.datelier"
    settings: tuple[ComparisonSettings, ...] = ()

    def move_pointer() -> None:
        nonlocal previous
        io = imgui.get_io()
        io.mouse_pos = imgui.ImVec2(*pointer)
        io.mouse_delta = imgui.ImVec2(
            pointer[0] - previous[0], pointer[1] - previous[1]
        )
        io.want_set_mouse_pos = True
        previous = pointer

    def start_click(pixel: tuple[float, float], target: int, frame: int) -> None:
        nonlocal pointer, click, click_frame, next_stage
        assert 0 < pixel[0] < 1280 and 0 < pixel[1] < 800, pixel
        pointer, click, click_frame, next_stage = pixel, 1, frame, target

    def hook(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered, click, click_frame, settings, initial_started
        io = imgui.get_io()
        if click:
            age = evidence.frames - click_frame
            if click == 1 and age > 3:
                io.add_mouse_button_event(0, True)
                click, click_frame = 2, evidence.frames
            elif click == 2 and age > 3:
                io.add_mouse_button_event(0, False)
                click, click_frame = 3, evidence.frames
            elif click == 3 and age > 6:
                click, stage, entered = 0, next_stage, evidence.frames
            return
        params = hello_imgui.get_runner_params()
        params.callbacks.post_new_frame = move_pointer
        if stage == 0:
            if mode == "save":
                editor.opening.request(
                    (root / "train.csv", root / "test.csv"), editor.active_id
                )
            stage = 1
        elif stage == 1:
            if (
                len(editor.files) != 2
                or any(f.loader.active is None for f in editor.files)
                or editor.workspace_jobs.busy
            ):
                return
            train, test = editor.files
            if mode == "save":
                assert test.loader.revision is not None
                test.editor.request(SetColumnRole("group", ColumnRole.CATEGORY))

                def mapped(a: str, b: str) -> tuple[ComparisonSource, ...]:
                    return (
                        ComparisonSource(
                            train.identity, a, "Training", (0.2, 0.55, 1.0, 1.0)
                        ),
                        ComparisonSource(
                            test.identity, b, "Test", (1.0, 0.5, 0.15, 1.0)
                        ),
                    )

                settings = (
                    ComparisonSettings(mapped("x", "different"), bins=2),
                    ComparisonSettings(
                        mapped("category", "group"),
                        category_limit=2,
                        normalization=Normalization.COUNT,
                    ),
                )
                editor.comparisons = settings
            else:
                settings = read_session_workspace(workspace).comparisons
                assert editor.comparisons == settings
                assert train.selection.row_ids == frozenset((1, 3))
                assert test.selection.row_ids == frozenset((0,))
            window = imgui.internal.find_window_by_name("Compare files")
            imgui.internal.set_window_dock(window, 0, imgui.Cond_.always)
            imgui.set_window_pos("Compare files", (20, 65), imgui.Cond_.always)
            imgui.set_window_size("Compare files", (1050, 725), imgui.Cond_.always)
            params.docking_params.focus_dockable_window("Compare files")
            stage, entered = 2, evidence.frames
        elif stage == 2:
            if (
                editor.comparison_jobs.busy
                or any(f.editor.busy for f in editor.files)
                or evidence.frames < entered + 8
            ):
                return
            if mode == "save":
                test = editor.files[1]
                assert test.loader.revision is not None
                test.selection.choose(test.loader.revision, (0,))
            assert len(editor.comparison_jobs.states) == 2
            assert all(s.result is not None for s in editor.comparison_jobs.states), [
                s.message for s in editor.comparison_jobs.states
            ]
            numeric = editor.comparison_jobs.states[0].result
            assert numeric is not None and numeric.edges == (0, 1.5, 3)
            assert [s.counts.tolist() for s in numeric.series] == [[2, 2], [1, 1]]
            if mode == "restore":
                bad = ComparisonSettings(
                    (settings[0].sources[0], settings[1].sources[1])
                )
                editor.comparisons = (bad, *settings)
                stage, entered = 3, evidence.frames
            else:
                stage = 5
        elif stage == 3:
            if editor.comparison_jobs.busy or evidence.frames < entered + 8:
                return
            assert "compatible" in editor.comparison_jobs.states[0].message
            assert editor.comparison_jobs.states[0].result is None
            editor.comparisons = settings[::-1]
            stage, entered = 4, evidence.frames
        elif stage == 4:
            if editor.comparison_jobs.busy or evidence.frames < entered + 8:
                return
            result = editor.comparison_jobs.states[0].result
            assert result is not None and result.keys == ("b", "a")
            assert [s.counts.tolist() for s in result.series] == [[2, 2, 0], [1, 0, 1]]
            stage = 5
        elif stage == 5:
            initial_started = editor.comparison_jobs.started
            start_click(evidence.comparison_settings_pixel, 6, evidence.frames)
        elif stage == 6:
            window = imgui.internal.find_window_by_name("Compare files")
            if evidence.comparison_apply_pixel[1] > 775:
                imgui.internal.set_scroll_y(window, window.scroll_max.y)
                entered = evidence.frames
                return
            if evidence.frames > entered + 3:
                start_click(evidence.comparison_apply_pixel, 7, evidence.frames)
        elif stage == 7:
            if editor.comparison_jobs.busy:
                return
            assert editor.comparison_jobs.started == initial_started + 1
            window = imgui.internal.find_window_by_name("Compare files")
            imgui.internal.set_scroll_y(window, 0)
            stage, entered = 8, evidence.frames
        elif stage == 8 and evidence.frames > entered + 5:
            start_click(evidence.comparison_settings_pixel, 9, evidence.frames)
        elif stage == 9:
            if evidence.frames > entered + 5:
                start_click(evidence.comparison_select_pixel, 10, evidence.frames)
        elif stage == 10:
            if editor.comparison_jobs.busy:
                return
            train, test = editor.files
            expected = (1, 3) if mode == "save" else (1, 2)
            assert train.selection.row_ids == frozenset(expected)
            assert test.selection.row_ids == frozenset((0,)) and editor.active is train
            assert all(
                not f.analysis.jobs.busy and not f.analysis.jobs.results
                for f in editor.files
            )
            assert evidence.comparison_frames > 5
            if mode == "save":
                editor.save_workspace(
                    workspace, layout=imgui.save_ini_settings_to_memory()
                )
                stage = 11
            else:
                params.app_shall_exit = True
                stage = 12
        elif stage == 11 and editor.workspace_jobs.saved is not None:
            params.app_shall_exit = True
            stage = 12

    evidence = run_gui(
        smoke_frames=1000,
        on_editor_frame=hook,
        initial_workspace=workspace if mode == "restore" else None,
    )
    assert stage == 12, (stage, evidence.frames)
    screenshot = hello_imgui.final_app_window_screenshot()
    if screenshot is not None:
        height, width = screenshot.shape[:2]
        Path(f"/tmp/datelier-comparison-{mode}.ppm").write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + screenshot[:, :, :3].tobytes()
        )
    print(
        json.dumps(
            {
                "mode": mode,
                "pid": os.getpid(),
                "frames": evidence.frames,
                "comparison_frames": evidence.comparison_frames,
                "native_apply_and_selection": True,
                "implicit_ml_runs": 0,
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--mode", choices=("save", "restore"))
    args = parser.parse_args()
    if args.root is not None:
        stage_run(args.root, args.mode)
        return
    with TemporaryDirectory(prefix="datelier-comparison-smoke-") as directory:
        root = Path(directory)
        train, test = root / "train.csv", root / "test.csv"
        train.write_text("x,category\n3,a\n0,b\n2,b\n1,a\n")
        test.write_text("different,group\n0,b\n3,c\n")
        original = (train.read_bytes(), test.read_bytes())
        for mode in ("save", "restore"):
            subprocess.run(
                [sys.executable, __file__, "--root", str(root), "--mode", mode],
                check=True,
            )
        assert (train.read_bytes(), test.read_bytes()) == original
        print(
            json.dumps(
                {
                    "source_bytes_unchanged": True,
                    "fresh_process_restore": True,
                    "incompatible_mapping_diagnostic": True,
                }
            )
        )


if __name__ == "__main__":
    main()
