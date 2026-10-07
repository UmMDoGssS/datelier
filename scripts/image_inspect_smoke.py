"""Native image focus, zoom/pan/channels/pixels and fresh-process workspace reopen."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs


def run(root: Path, output: Path, *, restore: bool) -> dict[str, object]:
    pixels: dict[str, tuple[float, float]] = {}
    original_checkbox, original_combo = imgui.checkbox, imgui.combo
    original_invisible = imgui.invisible_button
    navigation: dict[str, object] = {}
    navigation_log: list[dict[str, object]] = []
    started = False
    action = phase = entered = 0
    actions = (
        ["restored"]
        if restore
        else [
            "Gallery",
            "Fit image",
            "1:1 pixels",
            "pixel",
            "zoom",
            "pan",
            "Image channels",
            "G",
            "save",
        ]
    )
    expected_zoom = 1.0
    pan_left = 0.0
    observed_pixel = False
    failure: dict[str, object] = {}

    def capture(label: str) -> None:
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        pixels[label] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)

    def checkbox(label: str, checked: bool) -> tuple[bool, bool]:
        result = original_checkbox(label, checked)
        if label == "Gallery":
            capture(label)
        return result

    def combo(
        label: str, current: int, items: list[str], popup_max_height_in_items: int = -1
    ) -> tuple[bool, int]:
        result = original_combo(label, current, items, popup_max_height_in_items)
        if label == "##Image channels":
            capture("Image channels")
            lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
            pixels["G"] = (
                lo.x + 30,
                hi.y
                + imgui.get_style().frame_padding.y
                + imgui.get_text_line_height() / 2
                + 2 * imgui.get_text_line_height_with_spacing(),
            )
        return result

    def invisible(label: str, size: tuple[float, float], flags: int = 0) -> bool:
        result = original_invisible(label, size, flags)
        if label == "Image canvas":
            io = imgui.get_io()
            navigation.update(
                active=imgui.is_item_active(),
                hovered=imgui.is_item_hovered(),
                dragging=imgui.is_mouse_dragging(0),
                down=io.mouse_down[0],
                delta=[io.mouse_delta.x, io.mouse_delta.y],
                mouse=[io.mouse_pos.x, io.mouse_pos.y],
            )
        return result

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal \
            started, \
            action, \
            phase, \
            entered, \
            expected_zoom, \
            pan_left, \
            observed_pixel
        file = editor.active
        if file.loader.active is None:
            ready = next((f for f in editor.file_sessions if f.loader.active), None)
            if restore and ready:
                editor.activate(ready.identity)
            return
        params = hello_imgui.get_runner_params()
        if not started:
            if restore:
                assert (
                    file.exploration.active_tab == "Inspect"
                    and not file.inspect.settings.gallery
                )
                assert file.images.settings.display.channel == 1
                assert (
                    file.images.settings.viewport.zoom > 1
                    and file.images.settings.viewport.left > 0
                )
                assert file.images.jobs.store.temporary_path is None
            else:
                file.exploration.tab = "Inspect"
            params.docking_params.focus_dockable_window("Explore")
            started, entered = True, evidence.frames
        if action == len(actions):
            if (restore and evidence.frames >= 80) or (
                not restore and editor.workspace_jobs.saved is not None
            ):
                params.app_shall_exit = True
            return
        age, target = evidence.frames - entered, actions[action]
        if target == "pan" and phase in (2, 3, 4):
            navigation_log.append(dict(navigation, phase=phase))
        io = imgui.get_io()
        canvas = file.images.canvas
        pixels.update(file.images.buttons)
        if target in ("save", "restored"):
            if file.images.jobs.active is None or canvas.shown < 5 or age < 12:
                return
            assert file.images.jobs.active.locator.origin.row_id == 0
            assert file.images.settings.display.channel == 1
            if not restore:
                editor.save_workspace(
                    root / "session.datelier.json",
                    layout=imgui.save_ini_settings_to_memory(),
                )
            action, phase, entered = action + 1, 0, evidence.frames
            return
        if target in ("Gallery", "Image channels", "G", "Fit image", "1:1 pixels"):
            if phase == 0 and age > 10 and target in pixels:
                io.mouse_pos = imgui.ImVec2(*pixels[target])
                io.want_set_mouse_pos = True
                phase, entered = 1, evidence.frames
            elif phase == 1 and age > 3:
                io.add_mouse_button_event(0, True)
                phase, entered = 2, evidence.frames
            elif phase == 2 and age > 3:
                io.add_mouse_button_event(0, False)
                phase, entered = 3, evidence.frames
            elif phase >= 3 and age > 5:
                if target == "Gallery":
                    assert not file.inspect.settings.gallery
                elif target == "Fit image":
                    assert file.images.settings.viewport.zoom < 1
                elif target == "1:1 pixels":
                    assert file.images.settings.viewport.zoom == 1
                elif target == "G":
                    assert file.images.settings.display.channel == 1
                action, phase, entered = action + 1, 0, evidence.frames
            return
        if canvas.bounds is None or file.images.jobs.active is None:
            return
        x, y, width, height = canvas.bounds
        point = (x + min(100, width / 2), y + min(100, height / 2))
        if phase == 0 and age > 8:
            io.mouse_pos = imgui.ImVec2(*point)
            io.want_set_mouse_pos = True
            phase, entered = 1, evidence.frames
        elif phase == 1 and age > 5:
            if target == "pixel":
                if canvas.hovered is None or canvas.readout is None:
                    failure.update(
                        bounds=canvas.bounds,
                        mouse=[io.mouse_pos.x, io.mouse_pos.y],
                        message=file.images.jobs.message,
                    )
                    params.app_shall_exit = True
                    return
                px, py = canvas.hovered
                assert canvas.readout == (px % 256, py % 256, (px + py) % 256)
                observed_pixel = True
                action, phase, entered = action + 1, 0, evidence.frames
            elif target == "zoom":
                expected_zoom = file.images.settings.viewport.zoom
                io.add_mouse_wheel_event(0, 2)
                phase, entered = 2, evidence.frames
            else:
                pan_left = file.images.settings.viewport.left
                io.add_mouse_button_event(0, True)
                phase, entered = 2, evidence.frames
        elif phase == 2 and age > 6:
            if target == "zoom":
                assert file.images.settings.viewport.zoom > expected_zoom
                action, phase, entered = action + 1, 0, evidence.frames
            else:
                io.mouse_pos = imgui.ImVec2(point[0] - 40, point[1] - 20)
                io.want_set_mouse_pos = True
                phase, entered = 3, evidence.frames
        elif phase == 3 and age > 6:
            io.add_mouse_button_event(0, False)
            phase, entered = 4, evidence.frames
        elif phase == 4 and age > 6:
            if file.images.settings.viewport.left <= pan_left:
                failure.update(
                    navigation=navigation_log,
                    left=pan_left,
                    viewport=str(file.images.settings.viewport),
                )
                params.app_shall_exit = True
                return
            action, phase, entered = action + 1, 0, evidence.frames

    with (
        patch.object(imgui, "checkbox", new=checkbox),
        patch.object(imgui, "combo", new=combo),
        patch.object(imgui, "invisible_button", new=invisible),
    ):
        evidence = run_gui(
            None if restore else root / "source.csv",
            initial_workspace=root / "session.datelier.json" if restore else None,
            smoke_frames=900,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    output.mkdir(parents=True, exist_ok=True)
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / ("image-restored.png" if restore else "image-inspect.png")
    )
    assert not failure, failure
    assert action == len(actions), (action, actions[action:], pixels)
    p95 = float(np.percentile(evidence.frame_intervals_ms[10:], 95))
    assert p95 < 33
    return {
        "frames": evidence.frames,
        "frame_p95_ms": p95,
        "native_pixel_readout": observed_pixel,
        "native_fit_zoom_pan_channels": not restore,
        "restore": restore,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-image-inspect")
    )
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, args.output, restore=True)))
        return
    with TemporaryDirectory(prefix="datelier-image-inspect-") as directory:
        root = Path(directory)
        y, x = np.indices((1536, 2048))
        rgba = np.stack((x % 256, y % 256, (x + y) % 256), axis=2).astype(np.uint8)
        Image.fromarray(rgba).save(root / "image.png")
        (root / "source.csv").write_text("id,image,label\n1,image.png,gradient\n")
        before = hashlib.sha256((root / "image.png").read_bytes()).hexdigest()
        first = run(root, args.output, restore=False)
        completed = subprocess.run(
            [
                sys.executable,
                __file__,
                "--restore",
                str(root),
                "--output",
                str(args.output),
            ],
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        assert before == hashlib.sha256((root / "image.png").read_bytes()).hexdigest()
        report = {
            "save": first,
            "reopen": json.loads(completed.stdout.strip().splitlines()[-1]),
            "source_preserved": True,
        }
        (args.output / "image-native.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
