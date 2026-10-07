"""Native numeric channels/slices/ranges, exact hover and independent restore."""

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
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
from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
)
from datelier.inspection.heatmaps import Colormap
from datelier.pipeline.operations import Sort


def run(root: Path, output: Path, restore: bool) -> dict[str, object]:
    pixels: dict[str, tuple[float, float]] = {}
    originals = (
        imgui.button,
        imgui.collapsing_header,
        imgui.input_int,
        imgui.input_double,
        imgui.begin_combo,
        imgui.selectable,
    )
    actions = (
        ["restored"]
        if restore
        else [
            "channel=1",
            "Heatmap slice",
            "slice=1",
            "Heatmap slice",
            "Heatmap colors",
            "blue red",
            "Heatmap display range",
            "minimum=-25",
            "maximum=25",
            "Apply display range",
            "Heatmap display range",
            "Fit image",
            "pixel",
            "zoom",
            "Fit image",
            "save",
        ]
    )
    stage = action = phase = entered = 0
    restore_phase = 0
    zoom = 0.0
    report: dict[str, object] = {}

    def capture(label: str, *, input_field: bool = False) -> None:
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        pixels[label] = (
            lo.x + 35 if input_field else (lo.x + hi.x) / 2,
            (lo.y + hi.y) / 2,
        )

    def button(label: str, size: imgui.ImVec2 | None = None) -> bool:
        result = originals[0](label, size)
        if imgui.is_item_visible():
            capture(label)
        else:
            pixels.pop(label, None)
        return result

    def header(label: str, *args, **kwargs):
        result = originals[1](label, *args, **kwargs)
        capture(label)
        return result

    def integer(label: str, value: int, *args, **kwargs):
        result = originals[2](label, value, *args, **kwargs)
        if label.startswith("Heatmap channel"):
            capture("channel", input_field=True)
        elif label.startswith("Heatmap axis 1"):
            capture("slice", input_field=True)
        return result

    def double(label: str, value: float, *args, **kwargs):
        result = originals[3](label, value, *args, **kwargs)
        if label in ("Display minimum", "Display maximum"):
            capture(
                "minimum" if label.endswith("minimum") else "maximum", input_field=True
            )
        return result

    def combo(label: str, preview: str, *args, **kwargs):
        result = originals[4](label, preview, *args, **kwargs)
        if label == "Heatmap colors":
            capture(label)
        return result

    def selectable(label: str, selected: bool = False, *args, **kwargs):
        result = originals[5](label, selected, *args, **kwargs)
        if label == Colormap.BLUE_RED.value:
            capture("blue red")
        return result

    def large_layout(params, callbacks) -> None:
        configure_layout(params, callbacks)
        params.docking_params.docking_splits = []
        for window in params.docking_params.dockable_windows:
            window.dock_space_name = "MainDockSpace"

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, action, phase, entered, zoom, restore_phase
        parent = editor.active
        if parent.loader.active is None or parent.arrays.catalog is None:
            if restore:
                ready = next(
                    (file for file in editor.files if file.loader.active), None
                )
                if ready:
                    editor.activate(ready.identity)
            return
        file = parent.record_views.active(parent)
        age = evidence.frames - entered
        params, io = hello_imgui.get_runner_params(), imgui.get_io()
        if stage == 0:
            if restore:
                if file.deferred is not None:
                    params.docking_params.focus_dockable_window("Table preview")
                    assert parent.arrays.store.extractions == 0
                    report["metadata_only_restore"] = True
                    target = pixels.get("Prepare saved array records")
                    if restore_phase == 0 and age > 10 and target is not None:
                        io.mouse_pos = imgui.ImVec2(*target)
                        io.want_set_mouse_pos = True
                        restore_phase, entered = 1, evidence.frames
                    elif restore_phase == 1 and age > 3:
                        io.add_mouse_button_event(0, True)
                        restore_phase, entered = 2, evidence.frames
                    elif restore_phase == 2 and age > 3:
                        io.add_mouse_button_event(0, False)
                        restore_phase, entered = 3, evidence.frames
                    return
                if file is parent or file.loader.active is None:
                    return
                display = file.images.settings.display
                assert display.channel == 1 and display.fixed[1] == 1
                assert (
                    display.colormap == Colormap.BLUE_RED
                    and display.value_range == (-25, 25)
                )
                assert (
                    not file.images.profile_jobs.busy
                    and file.images.profile_jobs.active is None
                )
                report["restored_recipe"] = True
                params.docking_params.focus_dockable_window("Explore")
                stage, entered = 3, evidence.frames
            else:
                assert parent.arrays.store.extractions == 0
                parent.record_views.open_array(
                    parent,
                    ArrayRecordMapping(
                        "heat",
                        layout=ArrayLayout.HEATMAP,
                        display_axes=(3, 4),
                        channel_axis=2,
                        supporting=(SupportingArray("labels", "label"),),
                    ),
                )
                stage, entered = 1, evidence.frames
        elif stage == 1 and file is not parent and file.loader.active is not None:
            file.editor.request(Sort(("label",)))
            stage, entered = 2, evidence.frames
        elif stage == 2 and not file.editor.busy and age > 6:
            assert (
                file.loader.active is not None
                and file.loader.active.dataset.row_ids.to_list() == [1, 0]
            )
            file.inspect.settings = replace(file.inspect.settings, gallery=False)
            file.exploration.tab = "Inspect"
            params.docking_params.focus_dockable_window("Explore")
            stage, entered = 3, evidence.frames
        if stage < 3:
            return
        if action == len(actions):
            if (restore and evidence.frames >= 80) or (
                not restore and editor.workspace_jobs.saved is not None
            ):
                params.app_shall_exit = True
            return
        target = actions[action]
        prepared, canvas = file.images.jobs.active, file.images.canvas
        if target in ("save", "restored"):
            if age < 10 or prepared is None:
                return
            assert (
                prepared.locator.origin.row_id == 1
                and prepared.locator.origin.file_id == file.identity
            )
            assert prepared.pixel(10, 10) == (-10.0,)
            assert prepared.nonfinite == 3 and prepared.finite_range == (-47, 90)
            assert (
                prepared.display_range == (-25, 25) and not prepared.raw.flags.writeable
            )
            assert prepared.display.colormap == Colormap.BLUE_RED
            page = file.inspect.jobs.get(file.inspect.settings.focus)
            assert page is not None
            assert (
                next(f.text for f in page.cards[0].fields if f.name == "label") == "1"
            )
            # Restore prepares scalar support in a short-lived worker store;
            # the shared editor store then extracts only the visible heat member.
            assert parent.arrays.store.extractions == (1 if restore else 2), (
                parent.arrays.store.extractions
            )
            assert prepared.retained_bytes <= file.images.settings.cpu_bytes
            assert canvas.retained_bytes <= file.images.settings.gpu_bytes
            report.update(
                nonfinite=3,
                raw_value=-10,
                raw_bounds=[-47, 90],
                display_range=[-25, 25],
                source_row=1,
                aligned_label=1,
                shared_member_extractions=parent.arrays.store.extractions,
                retained_cpu_bytes=prepared.retained_bytes,
                retained_gpu_bytes=canvas.retained_bytes,
            )
            if not restore:
                editor.save_workspace(
                    root / "session.datelier.json",
                    layout=imgui.save_ini_settings_to_memory(),
                )
            action, phase, entered = action + 1, 0, evidence.frames
            return
        if target in ("pixel", "zoom"):
            if prepared is None or canvas.bounds is None:
                return
            if phase == 0 and age > 8:
                x, y, _, _ = canvas.bounds
                view = file.images.settings.viewport
                io.mouse_pos = imgui.ImVec2(
                    x + (10.5 - view.left) * view.zoom,
                    y + (10.5 - view.top) * view.zoom,
                )
                io.want_set_mouse_pos = True
                phase, entered = 1, evidence.frames
            elif phase == 1 and age > 6:
                if target == "pixel":
                    assert canvas.hovered == (10, 10) and canvas.readout == (-10.0,), (
                        canvas.bounds,
                        canvas.hovered,
                        canvas.readout,
                    )
                    report["native_raw_hover"] = True
                    action, phase, entered = action + 1, 0, evidence.frames
                else:
                    zoom = file.images.settings.viewport.zoom
                    io.add_mouse_wheel_event(0, 1)
                    phase, entered = 2, evidence.frames
            elif phase == 2 and age > 6:
                assert file.images.settings.viewport.zoom > zoom
                report["native_zoom"] = True
                action, phase, entered = action + 1, 0, evidence.frames
            return
        key = target.split("=")[0]
        if phase == 0 and age > 8 and key in pixels:
            io.mouse_pos = imgui.ImVec2(*pixels[key])
            io.want_set_mouse_pos = True
            phase, entered = 1, evidence.frames
        elif phase == 1 and age > 3:
            io.add_mouse_button_event(0, True)
            phase, entered = 2, evidence.frames
        elif phase == 2 and age > 3:
            io.add_mouse_button_event(0, False)
            if "=" in target:
                io.add_key_event(imgui.Key.left_ctrl, True)
                io.add_key_event(imgui.Key.a, True)
                phase, entered = 3, evidence.frames
            else:
                phase, entered = 6, evidence.frames
        elif phase == 3 and age > 3:
            io.add_key_event(imgui.Key.a, False)
            io.add_key_event(imgui.Key.left_ctrl, False)
            io.add_input_characters_utf8(target.split("=")[1])
            phase, entered = 4, evidence.frames
        elif phase == 4 and age > 3:
            io.add_key_event(imgui.Key.enter, True)
            phase, entered = 5, evidence.frames
        elif phase == 5 and age > 3:
            io.add_key_event(imgui.Key.enter, False)
            phase, entered = 6, evidence.frames
        elif phase == 6 and age > 7:
            action, phase, entered = action + 1, 0, evidence.frames

    with (
        patch.object(imgui, "button", button),
        patch.object(imgui, "collapsing_header", header),
        patch.object(imgui, "input_int", integer),
        patch.object(imgui, "input_double", double),
        patch.object(imgui, "begin_combo", combo),
        patch.object(imgui, "selectable", selectable),
        patch("datelier.gui.app.configure_layout", large_layout),
    ):
        evidence = run_gui(
            None if restore else root / "heatmaps.npz",
            initial_workspace=root / "session.datelier.json" if restore else None,
            smoke_frames=1200,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    output.mkdir(parents=True, exist_ok=True)
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / ("heatmap-restored.png" if restore else "heatmap-inspect.png")
    )
    assert action == len(actions), (
        stage,
        action,
        actions[action:],
        restore_phase,
        pixels,
        report,
    )
    p95 = float(np.percentile(evidence.frame_intervals_ms[10:], 95))
    assert p95 < 33
    report.update(frames=evidence.frames, frame_p95_ms=p95, restore=restore)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-heatmap-native")
    )
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, args.output, True)))
        return
    with TemporaryDirectory(prefix="datelier-heatmap-smoke-") as directory:
        root = Path(directory)
        raw = np.empty((2, 2, 2, 32, 48), dtype=np.float64)
        y, x = np.indices((32, 48))
        for record in range(2):
            for depth in range(2):
                for channel in range(2):
                    raw[record, depth, channel] = (
                        y * 3 + x - 180 + record * 100 + depth * 20 + channel * 10
                    )
        raw[0, 0, 0] = -5
        raw[1, 1, 1, 0, :3] = [np.nan, np.inf, -np.inf]
        source = root / "heatmaps.npz"
        np.savez_compressed(source, heat=raw, labels=np.array([2, 1]))
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        first = run(root, args.output, False)
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
        assert hashlib.sha256(source.read_bytes()).hexdigest() == before
        report = {
            "save": first,
            "reopen": json.loads(completed.stdout.strip().splitlines()[-1]),
            "source_preserved": True,
        }
        (args.output / "heatmap-native.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
