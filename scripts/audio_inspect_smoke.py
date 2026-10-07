"""Native audio metadata/profile/sample controls and idle fresh-process restore."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import soundfile as sf
from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
)
from datelier.pipeline.operations import Sort


def run(root: Path, output: Path, *, restore: bool, array: bool) -> dict[str, object]:
    pixels: dict[str, tuple[float, float]] = {}
    clips: dict[str, tuple[float, float]] = {}
    scroll_points: dict[str, tuple[float, float]] = {}
    original_checkbox, original_int, original_double = (
        imgui.checkbox,
        imgui.input_int,
        imgui.input_double,
    )
    original_button = imgui.button
    phase = action = entered = stage = 0
    ready = False
    actions = (
        [*(("Prepare saved array records",) if array else ()), "restored"]
        if restore
        else [
            "Gallery",
            *(("Array sample rate (Hz; 0 = unknown)=8000",) if array else ()),
            "End sample frame (exclusive)=1024",
            "Use original clipping rails",
            "Clipping amplitude=0.2",
            "Silence amplitude=0.005",
            "Sample channel (1-based)=2",
            "Prepare sample window",
            "Profile complete audio",
            "save",
        ]
    )

    def capture(label: str, numeric: bool = False) -> None:
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        pixels[label] = (lo.x + 40 if numeric else (lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
        position, size = imgui.get_window_pos(), imgui.get_window_size()
        clips[label] = (position.y + 25, position.y + size.y - 20)
        scroll_points[label] = (position.x + size.x - 7, position.y + size.y / 2)

    def checkbox(label: str, value: bool) -> tuple[bool, bool]:
        result = original_checkbox(label, value)
        if label in ("Gallery", "Use original clipping rails"):
            capture(label)
        return result

    def button(label: str, size: imgui.ImVec2 | None = None) -> bool:
        result = original_button(label, size)
        capture(label)
        return result

    def integer(
        label: str, value: int, step: int = 1, step_fast: int = 100, flags: int = 0
    ) -> tuple[bool, int]:
        result = original_int(label, value, step, step_fast, flags)
        capture(label, True)
        return result

    def double(
        label: str,
        value: float,
        step: float = 0,
        step_fast: float = 0,
        format: str = "%.6f",
        flags: int = 0,
    ) -> tuple[bool, float]:
        result = original_double(label, value, step, step_fast, format, flags)
        capture(label, True)
        return result

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal phase, action, entered, ready, stage
        owner = editor.active
        if owner.loader.active is None:
            return
        file = owner.record_views.active(owner)
        params, io = hello_imgui.get_runner_params(), imgui.get_io()
        if array and not restore and stage < 3:
            if stage == 0 and owner.arrays.catalog is not None:
                owner.record_views.open_array(
                    owner,
                    ArrayRecordMapping(
                        "waves",
                        layout=ArrayLayout.AUDIO,
                        display_axes=(1,),
                        channel_axis=2,
                        supporting=(SupportingArray("labels", "label"),),
                    ),
                )
                stage = 1
            elif stage == 1 and file is not owner and file.loader.active is not None:
                file.editor.request(Sort(("label",)))
                stage, entered = 2, evidence.frames
            elif stage == 2 and not file.editor.busy and evidence.frames - entered > 8:
                assert (
                    file.loader.active is not None
                    and file.loader.active.dataset.row_ids.to_list() == [1, 2, 0]
                )
                stage = 3
            return
        if file.loader.active is None:
            if restore and array and file.deferred is not None:
                age = evidence.frames - entered
                if phase == 0 and age > 8 and "Prepare saved array records" in pixels:
                    io.mouse_pos = imgui.ImVec2(*pixels["Prepare saved array records"])
                    io.want_set_mouse_pos = True
                    phase, entered = 1, evidence.frames
                elif phase == 1 and age > 3:
                    io.add_mouse_button_event(0, True)
                    phase, entered = 2, evidence.frames
                elif phase == 2 and age > 3:
                    io.add_mouse_button_event(0, False)
                    phase, entered = 3, evidence.frames
            return
        if restore and array and action == 0:
            action, phase, entered = 1, 0, evidence.frames
        if not ready:
            if not restore:
                file.exploration.tab = "Inspect"
            else:
                assert not file.inspect.settings.gallery
                assert file.audio.settings.thresholds.clipping == 0.2
                assert file.audio.settings.thresholds.silence == 0.005
                assert file.audio.settings.channel == 1
                assert file.audio.settings.range.stop == 1024
            params.docking_params.focus_dockable_window("Explore")
            ready, entered = True, evidence.frames
        if action == len(actions):
            if restore or editor.workspace_jobs.saved is not None:
                params.app_shall_exit = True
            return
        target, age = actions[action], evidence.frames - entered
        pixels.update(file.audio.buttons)
        if target == "restored":
            if file.audio.jobs.metadata is not None and age > 25:
                assert file.audio.jobs.profile is file.audio.jobs.active is None
                assert not file.audio.jobs.busy
                assert file.audio.jobs.metadata[0].origin.row_id == (1 if array else 0)
                action += 1
            return
        if target == "save":
            if (
                file.audio.jobs.profile is None
                or file.audio.jobs.active is None
                or age < 12
            ):
                return
            profile, samples = file.audio.jobs.profile, file.audio.jobs.active
            assert (
                profile.locator.origin.row_id
                == samples.locator.origin.row_id
                == (1 if array else 0)
            )
            assert (
                profile.metadata.sample_rate == 8000 and profile.channels[1].rms == 0.5
            )
            assert profile.channels[1].clipped == 8000
            assert np.all(samples.raw[:, 1] == -0.5) and samples.raw.shape == (1024, 2)
            if file.audio.rendered_samples == 0:
                io.mouse_pos = imgui.ImVec2(
                    *scroll_points.get(
                        "Profile complete audio", (985, io.display_size.y - 80)
                    )
                )
                io.want_set_mouse_pos = True
                io.add_mouse_wheel_event(0, -3)
                return
            assert file.audio.rendered_samples < 100
            page = file.inspect.jobs.get(file.inspect.settings.focus)
            assert page is not None
            if array:
                assert any(
                    field.name == "label" and field.text == "1"
                    for field in page.cards[0].fields
                )
            editor.save_workspace(
                root / "session.datelier.json",
                layout=imgui.save_ini_settings_to_memory(),
            )
            action += 1
            return
        key = target.rsplit("=", 1)[0]
        if phase == 0 and age > 9 and key in pixels:
            top, bottom = clips.get(key, (430, io.display_size.y - 20))
            if not top <= pixels[key][1] <= bottom:
                io.mouse_pos = imgui.ImVec2(
                    *scroll_points.get(key, (985, (top + bottom) / 2))
                )
                io.want_set_mouse_pos = True
                io.add_mouse_wheel_event(0, -2 if pixels[key][1] > bottom else 2)
                entered = evidence.frames
                return
            if key == "Gallery":
                assert file.audio.jobs.active is file.audio.jobs.profile is None
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
            io.add_input_characters_utf8(target.rsplit("=", 1)[1])
            phase, entered = 4, evidence.frames
        elif phase == 4 and age > 3:
            io.add_key_event(imgui.Key.enter, True)
            phase, entered = 5, evidence.frames
        elif phase == 5 and age > 3:
            io.add_key_event(imgui.Key.enter, False)
            phase, entered = 6, evidence.frames
        elif phase == 6 and age > 7:
            if key == "Gallery":
                assert not file.inspect.settings.gallery
            action, phase, entered = action + 1, 0, evidence.frames

    with (
        patch.object(imgui, "button", button),
        patch.object(imgui, "checkbox", checkbox),
        patch.object(imgui, "input_int", integer),
        patch.object(imgui, "input_double", double),
    ):
        evidence = run_gui(
            None if restore else root / ("waves.npz" if array else "source.csv"),
            initial_workspace=root / "session.datelier.json" if restore else None,
            smoke_frames=900,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    output.mkdir(parents=True, exist_ok=True)
    name = "array" if array else "file"
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / (f"audio-{name}-restored.png" if restore else f"audio-{name}.png")
    )
    assert action == len(actions), (action, actions[action:], pixels)
    assert "sounddevice" not in sys.modules
    p95 = float(np.percentile(evidence.frame_intervals_ms[10:], 95))
    assert p95 < 33
    return {
        "frames": evidence.frames,
        "frame_p95_ms": p95,
        "restore": restore,
        "array": array,
        "source_row": 1 if array else 0,
        "native_controls": not restore,
        "restore_idle": restore,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--restore", type=Path)
    parser.add_argument("--array", action="store_true")
    args = parser.parse_args()
    if args.restore:
        print(
            json.dumps(run(args.restore, args.output, restore=True, array=args.array))
        )
        return
    with TemporaryDirectory(prefix="datelier-audio-inspect-") as temporary:
        root = Path(temporary)
        if args.array:
            values = np.empty((3, 8000, 2), dtype=np.float32)
            for record in range(3):
                values[record] = ((record + 1) * 0.25, -(record + 1) * 0.25)
            source = root / "waves.npz"
            np.savez_compressed(source, waves=values, labels=np.array([3, 1, 2]))
        else:
            source = root / "signal.wav"
            sf.write(source, np.tile([0.25, -0.5], (8000, 1)), 8000, subtype="DOUBLE")
            (root / "source.csv").write_text(
                "id,audio,label\n1,signal.wav,constant stereo\n"
            )
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        saved = run(root, args.output, restore=False, array=args.array)
        completed = subprocess.run(
            [
                sys.executable,
                __file__,
                "--restore",
                str(root),
                "--output",
                str(args.output),
                *(("--array",) if args.array else ()),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert completed.returncode == 0, completed.stderr
        assert hashlib.sha256(source.read_bytes()).hexdigest() == before
        report = {
            "save": saved,
            "restore": json.loads(completed.stdout.strip().splitlines()[-1]),
            "source_preserved": True,
        }
        (
            args.output
            / ("audio-array-native.json" if args.array else "audio-file-native.json")
        ).write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
