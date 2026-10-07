"""Native output selection, listening commands and fresh-process idle preferences."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import soundfile as sf
from audio_smoke_controls import NativeControls
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
from datelier.inspection.audio.playback.controller import PlaybackPhase
from datelier.pipeline.operations import Sort


def run(root: Path, output: Path, *, restore: bool, array: bool) -> dict[str, object]:
    controls = NativeControls()
    actions = (
        [*(("Prepare saved array records",) if array else ()), "reveal", "restored"]
        if restore
        else [
            "Gallery",
            *(("Array sample rate (Hz; 0 = unknown)=8000",) if array else ()),
            "Time start (s)=0.5",
            "Time end (s)=1.5",
            "Sample channel (1-based)=2",
            "Listen selected channel",
            "Playback volume=0.25",
            "Check audio outputs",
            "outputs",
            "Audio output",
            "Default Sink, PulseAudio",
            "Play audio",
            "playing",
            "Pause audio",
            "paused",
            "Seek time (s)=0.75",
            "Seek audio",
            "seeked",
            "Playback volume=0.125",
            "Resume audio",
            "resumed",
            "Stop audio",
            "stopped",
            "save",
        ]
    )
    action = stage = entered = 0
    started = False
    paused_position = 0
    result: dict[str, object] = {}

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal action, stage, entered, started, paused_position
        owner = editor.active
        if owner.loader.active is None:
            return
        file = owner.record_views.active(owner)
        params = hello_imgui.get_runner_params()
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
                stage = 3
            return
        if not started:
            if not restore:
                file.exploration.tab = "Inspect"
            params.docking_params.focus_dockable_window("Explore")
            started, entered = True, evidence.frames
        if action == len(actions):
            if restore or editor.workspace_jobs.saved is not None:
                params.app_shall_exit = True
            return
        target, age = actions[action], evidence.frames - entered
        state = editor.playback.snapshot
        assert state.phase != PlaybackPhase.FAILED, state.message
        if target == "reveal":
            key = "Seek audio"
            if key not in controls.points or age < 10:
                return
            top, bottom = controls.clips[key]
            if not top <= controls.points[key][1] <= bottom:
                io = imgui.get_io()
                io.mouse_pos = imgui.ImVec2(*controls.scroll[key])
                io.want_set_mouse_pos = True
                io.add_mouse_wheel_event(
                    0, -2 if controls.points[key][1] > bottom else 2
                )
                entered = evidence.frames
                return
        elif target == "outputs":
            if age < 15 or editor.playback.devices.busy:
                return
            queries = [choice.query for choice in editor.playback.devices.choices]
            assert "Default Sink, PulseAudio" in queries, (
                queries,
                editor.playback.devices.message,
            )
            result["output_choices"] = queries
        elif target == "playing":
            if state.phase != PlaybackPhase.PLAYING or state.position <= 4000:
                return
            assert state.request is not None
            assert state.request.locator.origin.row_id == (1 if array else 0)
            assert (
                state.request.range.start == 4000 and state.request.range.stop == 12000
            )
            assert state.request.channel == 1 and state.request.channels == 1
            assert state.request.metadata.sample_rate == 8000
            assert file.audio.settings.playback.volume == 0.25, (
                file.audio.settings.playback
            )
            result.update(
                source_row=state.request.locator.origin.row_id,
                device=state.device,
                retained_output_bytes=state.cpu_bytes,
                latency_ms=state.latency * 1000,
            )
        elif target == "paused":
            if state.phase != PlaybackPhase.PAUSED:
                return
            if age < 3:
                return
            if paused_position == 0:
                paused_position, entered = state.position, evidence.frames
                return
            if age < 20:
                return
            assert state.position == paused_position
            result["paused_cursor_stable"] = True
        elif target == "seeked":
            if state.phase != PlaybackPhase.PAUSED or state.position != 6000:
                return
            assert state.request is not None and state.request.first_frame == 6000
            result["seek_frame"] = 6000
        elif target == "resumed":
            if state.phase != PlaybackPhase.PLAYING or state.position <= 6000:
                return
            assert file.audio.settings.playback.volume == 0.125
            result["native_volume_changed"] = True
        elif target == "stopped":
            if state.phase != PlaybackPhase.IDLE:
                return
            assert state.cpu_bytes == 0
            result.update(device_closed=True, output_underruns=state.underruns)
        elif target in ("save", "restored"):
            if file.audio.jobs.metadata is None or age < (60 if restore else 15):
                return
            prefs = file.audio.settings.playback
            assert prefs.device == "Default Sink, PulseAudio" and prefs.volume == 0.125
            assert (
                prefs.selected_range
                and prefs.selected_channel
                and prefs.seek_frame == 6000
            )
            assert (
                file.audio.settings.channel == 1
                and file.audio.settings.range.start == 4000
                and file.audio.settings.range.stop == 12000
            )
            assert file.audio.jobs.active is file.audio.jobs.profile is None
            if restore:
                assert state.request is None and state.phase == PlaybackPhase.IDLE
                assert (
                    not editor.playback.devices.busy
                    and editor.playback.devices.choices == ()
                )
                assert "sounddevice" not in sys.modules
                result["restore_idle"] = True
            else:
                editor.save_workspace(
                    root / "session.datelier.json",
                    layout=imgui.save_ini_settings_to_memory(),
                )
            if array:
                assert (
                    file.loader.active is not None
                    and file.loader.active.dataset.table["label"][0] == 1
                )
            result["supporting_label"] = 1 if array else "quiet stereo"
        else:
            if controls.advance(target, evidence.frames):
                action, entered = action + 1, evidence.frames
            return
        action, entered = action + 1, evidence.frames

    with controls.patched():
        evidence = run_gui(
            None if restore else root / ("waves.npz" if array else "source.csv"),
            initial_workspace=root / "session.datelier.json" if restore else None,
            smoke_frames=2400,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    assert action == len(actions), (action, actions[action:], result, controls.points)
    output.mkdir(parents=True, exist_ok=True)
    name = "audio-listening-array" if array else "audio-listening-file"
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / (name + ("-restored.png" if restore else ".png"))
    )
    p95 = float(np.percentile(evidence.frame_intervals_ms[10:], 95))
    assert p95 < 33, (p95, result)
    return {
        **result,
        "frames": evidence.frames,
        "frame_p95_ms": p95,
        "restore": restore,
        "listening_observation": "Not recorded; native device/control instrumentation.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--restore", type=Path)
    parser.add_argument("--array", action="store_true")
    args = parser.parse_args()
    if args.restore:
        print(
            json.dumps(run(args.restore, args.output, restore=True, array=args.array))
        )
        return
    with TemporaryDirectory(prefix="datelier-listening-") as temporary:
        root = Path(temporary)
        positions = np.arange(16000) / 8000
        if args.array:
            values = np.empty((3, 16000, 2), dtype=np.float32)
            for row in range(3):
                values[row, :, 0] = 0.25 * np.sin(2 * np.pi * 440 * positions)
                values[row, :, 1] = 0.25 * np.cos(
                    2 * np.pi * (660 + 220 * row) * positions
                )
            source = root / "waves.npz"
            np.savez_compressed(source, waves=values, labels=np.array([3, 1, 2]))
        else:
            source = root / "tones.wav"
            sf.write(
                source,
                np.stack(
                    (
                        0.25 * np.sin(2 * np.pi * 440 * positions),
                        0.25 * np.cos(2 * np.pi * 660 * positions),
                    ),
                    axis=1,
                ),
                8000,
                subtype="DOUBLE",
            )
            (root / "source.csv").write_text(
                "id,audio,label\n1,tones.wav,quiet stereo\n"
            )
        original = hashlib.sha256(source.read_bytes()).hexdigest()
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
        assert hashlib.sha256(source.read_bytes()).hexdigest() == original
        report = {
            "save": saved,
            "restore": json.loads(completed.stdout.strip().splitlines()[-1]),
            "source_preserved": True,
        }
        (
            args.output
            / (
                "audio-listening-array-native.json"
                if args.array
                else "audio-listening-file-native.json"
            )
        ).write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
