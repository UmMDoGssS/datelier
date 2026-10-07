"""Native common image bins, source-scoped links and idle fresh-process restore."""

import argparse
import hashlib
import json
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.layout import configure_layout
from datelier.gui.tabs import EditorTabs
from datelier.inspection.references.types import ReferenceSettings
from datelier.pipeline.operations import Sort


def fixtures(root: Path) -> None:
    for name, width, red in (
        ("a2", 32, 10),
        ("a4", 64, 30),
        ("b6", 96, 50),
        ("b2", 32, 70),
    ):
        Image.new("RGB", (width, 32), (red, 20, 30)).save(root / f"{name}.png")
    (root / "first.csv").write_text("image,label\na2.png,z\na4.png,a\n")
    (root / "second.csv").write_text("image,label\nb6.png,z\nb2.png,a\n")


def run(root: Path, output: Path, restore: bool) -> dict[str, object]:
    pixels: dict[str, tuple[float, float]] = {}
    names = (
        "button",
        "collapsing_header",
        "begin_tab_item",
        "checkbox",
        "input_int",
        "combo",
        "selectable",
    )
    originals = {name: getattr(imgui, name) for name in names}

    def combo(label: str, current: int, items: list[str], *args) -> tuple[bool, int]:
        if label not in ("Image selection source", "Image dimension bin"):
            return wrapper("combo")(label, current, items, *args)
        opened = imgui.begin_combo(label, items[current])
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        pixels[label] = (lo.x + 35, (lo.y + hi.y) / 2)
        changed = False
        if opened:
            for index, item in enumerate(items):
                if imgui.selectable(item, index == current)[0]:
                    changed, current = True, index
                lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
                pixels[f"{label}>{index}"] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
            imgui.end_combo()
        return changed, current

    def wrapper(name: str):
        def wrapped(label, *args, **kwargs):
            result = originals[name](label, *args, **kwargs)
            if imgui.is_item_visible():
                lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
                pixels[label] = (
                    lo.x + 35 if name in ("input_int", "combo") else (lo.x + hi.x) / 2,
                    (lo.y + hi.y) / 2,
                )
            else:
                pixels.pop(label, None)
            return result

        return wrapped

    def layout(params, callbacks) -> None:
        configure_layout(params, callbacks)
        params.docking_params.docking_splits = []
        for window in params.docking_params.dockable_windows:
            window.dock_space_name = "MainDockSpace"

    actions = (
        ["Prepare image comparison", "ready", "Colors", "chart", "finish"]
        if restore
        else [
            "Images",
            "New image comparison",
            "Image mappings and scopes",
            "Include first.csv ",
            "Include second.csv ",
            "Common image bins=2",
            "Image mappings and scopes",
            "Prepare image comparison",
            "ready",
            "Compare proportions",
            "Image selection source>1",
            "Image dimension bin>1",
            "Select matching image rows",
            "selected",
            "Statistics",
            "statistics",
            "Records",
            "1##Image profile record",
            "record",
            "Colors",
            "chart",
            "finish",
        ]
    )
    stage = action = phase = entered = 0
    report: dict[str, object] = {"restore": restore}

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, action, phase, entered
        params, io = hello_imgui.get_runner_params(), imgui.get_io()
        if stage == 0:
            if not restore:
                editor.opening.request(
                    (root / "first.csv", root / "second.csv"), editor.active_id
                )
            stage = 1
        if stage == 1:
            if len(editor.files) != 2 or editor.workspace_jobs.busy:
                return
            if any(file.loader.active is None for file in editor.files):
                return
            for file in editor.files:
                assert file.loader.active is not None
                if file.references.settings.roots != (str(root),):
                    file.references.configure(ReferenceSettings(roots=(str(root),)))
                    return
                if (
                    file.references.source != file.loader.active.dataset.source.path
                    or file.references.busy
                    or file.references.index is None
                ):
                    return
            if restore:
                assert editor.image_comparison_jobs.started == 0
                assert editor.image_comparison_jobs.active is None
                assert editor.comparison_tab == "Images"
                assert editor.image_comparison_view.tab == "Colors"
                assert not editor.image_comparison_view.proportions
                assert editor.image_comparisons[0].bins == 2
                assert len(editor.image_comparisons[0].sources) == 2
                report["idle_saved_controls"] = True
                stage = 3
            else:
                editor.files[1].editor.request(Sort(("label",)))
                stage = 2
            entered = evidence.frames
        if stage == 2:
            second = editor.files[1]
            assert second.loader.active is not None
            if second.editor.busy or second.loader.active.dataset.row_ids.to_list() != [
                1,
                0,
            ]:
                return
            stage = 3
        if action == len(actions):
            if restore or editor.workspace_jobs.saved is not None:
                params.app_shall_exit = True
            return
        target, age = actions[action], evidence.frames - entered
        jobs = editor.image_comparison_jobs
        result = jobs.active
        if target in ("ready", "selected", "statistics", "record", "chart", "finish"):
            if age < 12:
                return
            if target == "ready":
                if result is None:
                    if age > 180 and not jobs.busy:
                        raise AssertionError(jobs.message)
                    return
                assert len(result.profiles) == 2
                assert [profile.ready for profile in result.profiles] == [2, 2]
                assert [
                    next(s.mean for s in profile.summaries if s.key.name == "R")
                    for profile in result.profiles
                ] == [70 / 3, 55]
                widths = next(
                    curve for curve in result.curves if curve.key.name == "Width"
                )
                for chart in widths.counts:
                    assert chart is not None
                    assert chart.edges.tolist() == [32, 64, 96]
                report["shared_bins_and_weighted_means"] = True
            elif target == "selected":
                second = editor.files[1]
                if second.selection.row_ids != {0}:
                    return
                assert editor.active is second and second.table.target_row == 2
                assert not editor.files[0].selection.row_ids
                report["native_bin_link_sorted_source"] = True
            elif target == "statistics":
                assert editor.image_comparison_view.tab == "Statistics"
                report["native_statistics"] = True
            elif target == "record":
                second = editor.files[1]
                if second.images.jobs.active is None:
                    return
                assert editor.active is second and second.selection.row_ids == {1}
                assert second.images.jobs.active.locator.origin.row_id == 1
                assert second.images.jobs.active.pixel(0, 0) == (70, 20, 30)
                report["native_record_to_inspect"] = True
            elif target == "chart":
                assert editor.image_comparison_view.tab == "Colors"
                assert editor.image_comparison_view.channel == "R"
                assert not editor.image_comparison_view.proportions
                report["native_color_legend"] = True
            else:
                assert editor.comparison_tab == "Images"
                if not restore:
                    editor.save_workspace(
                        root / "session.datelier.json",
                        layout=imgui.save_ini_settings_to_memory(),
                    )
            action, phase, entered = action + 1, 0, evidence.frames
            return
        key = target.split("=", 1)[0].split(">", 1)[0]
        if phase == 0 and age > 8:
            params.docking_params.focus_dockable_window("Compare files")
            phase, entered = 8, evidence.frames
        elif phase == 8 and age > 4 and key in pixels:
            io.mouse_pos = imgui.ImVec2(*pixels[key])
            io.want_set_mouse_pos = True
            phase, entered = 1, evidence.frames
        elif phase == 1 and age > 4:
            io.add_mouse_button_event(0, True)
            phase, entered = 2, evidence.frames
        elif phase == 2 and age > 4:
            io.add_mouse_button_event(0, False)
            if "=" in target:
                io.add_key_event(imgui.Key.left_ctrl, True)
                io.add_key_event(imgui.Key.mod_ctrl, True)
                io.add_key_event(imgui.Key.a, True)
                phase = 3
            elif ">" in target:
                phase = 9
            else:
                phase = 6
            entered = evidence.frames
        elif phase == 3 and age > 4:
            for keycode in (imgui.Key.a, imgui.Key.left_ctrl, imgui.Key.mod_ctrl):
                io.add_key_event(keycode, False)
            phase, entered = 4, evidence.frames
        elif phase == 4 and age > 4:
            io.add_input_characters_utf8(target.split("=", 1)[1])
            phase, entered = 5, evidence.frames
        elif phase == 9 and age > 4:
            if target not in pixels:
                return
            io.mouse_pos = imgui.ImVec2(*pixels[target])
            io.want_set_mouse_pos = True
            phase, entered = 10, evidence.frames
        elif phase == 10 and age > 4:
            io.add_mouse_button_event(0, True)
            phase, entered = 11, evidence.frames
        elif phase == 11 and age > 4:
            io.add_mouse_button_event(0, False)
            phase, entered = 6, evidence.frames
        elif phase == 5 and age > 4:
            io.add_key_event(imgui.Key.enter, True)
            phase, entered = 7, evidence.frames
        elif phase == 7 and age > 4:
            io.add_key_event(imgui.Key.enter, False)
            phase, entered = 6, evidence.frames
        elif phase == 6 and age > 8:
            if key == "Common image bins":
                assert editor.image_comparisons[0].bins == 2
            if key == "Image selection source":
                assert editor.image_comparison_view.source == 1
            if key == "Image dimension bin":
                assert editor.image_comparison_view.bin_index == 1
            action, phase, entered = action + 1, 0, evidence.frames

    with patch("datelier.gui.app.configure_layout", layout), ExitStack() as stack:
        for name in names:
            stack.enter_context(
                patch.object(imgui, name, combo if name == "combo" else wrapper(name))
            )
        evidence = run_gui(
            initial_workspace=root / "session.datelier.json" if restore else None,
            smoke_frames=1600,
            on_editor_frame=frame,
            preferences_path=root / "prefs.json",
        )
    assert action == len(actions), (actions[action], stage, phase, list(pixels))
    p95 = float(np.percentile(evidence.frame_intervals_ms[10:], 95))
    assert p95 < 33, p95
    output.mkdir(parents=True, exist_ok=True)
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / f"image-comparison{'-restored' if restore else ''}.png"
    )
    report.update(frames=evidence.frames, frame_p95_ms=p95)
    print(json.dumps(report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-image-comparison")
    )
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    if args.restore:
        assert args.root is not None
        run(args.root, args.output, True)
        return
    with TemporaryDirectory(prefix="datelier-image-comparison-") as directory:
        root = Path(directory)
        fixtures(root)
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.iterdir()
        }
        saved = run(root, args.output, False)
        child = subprocess.run(
            [
                sys.executable,
                __file__,
                "--restore",
                "--root",
                str(root),
                "--output",
                str(args.output),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        restored = json.loads(child.stdout.strip().splitlines()[-1])
        assert all(
            hashlib.sha256(path.read_bytes()).hexdigest() == digest
            for path, digest in before.items()
        )
        (args.output / "image-comparison-native.json").write_text(
            json.dumps(
                {"save": saved, "reopen": restored, "source_preserved": True}, indent=2
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
