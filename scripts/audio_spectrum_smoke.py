"""Native waveform/spectral settings, correct raster orientation and fresh restore."""

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
from datelier.inspection.audio.view_types import (
    AudioViewKind,
    AudioWindow,
    SpectralView,
    WaveformEnvelope,
)


def run(
    root: Path,
    output: Path,
    restore: bool,
    *,
    large_fft: bool = False,
    waveform_only: bool = False,
) -> dict[str, object]:
    controls = NativeControls()
    points, clips, scroll = controls.points, controls.clips, controls.scroll
    actions = (
        [
            "Gallery",
            "Sample channel (1-based)=2",
            "Spectrogram",
            "Signal settings",
            "Signal FFT length=65536",
            "Frequency display bins=32769",
            "Auto spectral color range",
            "Spectral color minimum=-120",
            "Spectral color maximum=-100",
            "Signal settings",
            "Expand",
            "hover",
            "large",
        ]
        if large_fft
        else ["Expand", "hover", "restored"]
        if restore
        else [
            "Gallery",
            "Time start (s)=0.5",
            "Time end (s)=1.5",
            "Sample channel (1-based)=2",
            "Expand",
            "waveform",
            "Restore",
            "Spectrogram",
            "Signal settings",
            "Signal FFT length=512",
            "Signal hop length=128",
            "Hamming",
            "Minimum frequency (Hz)=500",
            "Maximum frequency (Hz; 0 = Nyquist)=3000",
            "Decibel floor=-90",
            "Audio memory (MiB)=4",
            "Audio texture memory (MiB)=1",
            "Signal settings",
            "Expand",
            "hover",
            "save",
        ]
    )
    if waveform_only:
        actions = actions[:6]
    started = False
    action = phase = entered = 0
    result: dict[str, object] = {}
    expected_pixel: tuple[int, int, int] | None = None
    peak_pixel: tuple[int, int] | None = None
    timings: dict[str, list[float]] = {}

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal started, action, phase, entered, expected_pixel, peak_pixel
        if evidence.frame_intervals_ms:
            stage = actions[min(action, len(actions) - 1)]
            timings.setdefault(stage, []).append(evidence.frame_intervals_ms[-1])
        file = editor.active
        if file.loader.active is None:
            return
        io, params = imgui.get_io(), hello_imgui.get_runner_params()
        if not started:
            if not restore:
                file.exploration.tab = "Inspect"
            else:
                assert file.audio.settings.view.mode == AudioViewKind.SPECTROGRAM
                assert (
                    file.audio.settings.range.start == 4000
                    and file.audio.settings.range.stop == 12000
                )
                assert file.audio.settings.channel == 1
            params.docking_params.focus_dockable_window("Explore")
            started, entered = True, evidence.frames
        if action == len(actions):
            if (
                restore
                or large_fft
                or waveform_only
                or editor.workspace_jobs.saved is not None
            ):
                params.app_shall_exit = True
            return
        target, age = actions[action], evidence.frames - entered
        data = file.audio.signal.active
        if target == "waveform":
            if (
                isinstance(data, WaveformEnvelope)
                and age > 12
                and file.audio.canvas.shown > 3
            ):
                assert (
                    data.range.start == 4000
                    and data.range.stop == 12000
                    and data.channel == 1
                )
                assert np.allclose(data.minimum, -0.25) and np.allclose(
                    data.maximum, 0.25
                )
                result["native_waveform_extrema"] = True
                action, phase, entered = action + 1, 0, evidence.frames
            return
        if target == "hover":
            point = file.audio.canvas.peak_pixel
            if not isinstance(data, SpectralView) or point is None or age < 15:
                return
            if phase == 0:
                io.mouse_pos = imgui.ImVec2(*point)
                io.want_set_mouse_pos = True
                phase, entered = 1, evidence.frames
            elif age > 12 and file.audio.canvas.readout is not None:
                readout = file.audio.canvas.readout
                assert readout[1] == 2000 and readout[2] > 0
                peak_pixel = (round(point[0]), round(point[1]))
                color = data.color_pixel(*data.peak)
                expected_pixel = (int(color[0]), int(color[1]), int(color[2]))
                result["native_frequency_readout_hz"] = readout[1]
                action, phase, entered = action + 1, 0, evidence.frames
            return
        if target == "large":
            if not isinstance(data, SpectralView) or file.audio.signal.busy or age < 15:
                return
            assert data.power.shape == (32769, 1) and data.frequency_step == 1
            assert len(data.tiles) == len(file.audio.canvas.textures) == 17
            result.update(
                frequency_rows=32769,
                texture_tiles=17,
                gpu_bytes=file.audio.canvas.retained_bytes,
            )
            action, phase, entered = action + 1, 0, evidence.frames
            return
        if target in ("save", "restored"):
            if not isinstance(data, SpectralView) or file.audio.signal.busy or age < 15:
                return
            settings = file.audio.settings
            assert settings.view.fft == 512 and settings.view.hop == 128
            assert settings.view.window == AudioWindow.HAMMING
            assert (
                settings.view.frequency_low == 500
                and settings.view.frequency_high == 3000
            )
            assert settings.view.db_floor == -90 and settings.gpu_bytes == 1024**2
            assert data.locator.origin.row_id == 0 and data.metadata.sample_rate == 8000
            assert file.audio.jobs.profile is file.audio.jobs.active is None
            assert file.audio.canvas.retained_bytes <= settings.gpu_bytes
            result.update(
                cpu_bytes=data.retained_bytes,
                gpu_bytes=file.audio.canvas.retained_bytes,
                uploads=file.audio.canvas.uploads,
                tail_frames=data.tail_frames,
                restore_idle=restore,
            )
            if not restore:
                editor.save_workspace(
                    root / "session.datelier.json",
                    layout=imgui.save_ini_settings_to_memory(),
                )
            action, phase, entered = action + 1, 0, evidence.frames
            return
        key = target.rsplit("=", 1)[0]
        if phase == 0 and age > 9 and key in points:
            top, bottom = clips[key]
            if not top <= points[key][1] <= bottom:
                io.mouse_pos = imgui.ImVec2(*scroll[key])
                io.want_set_mouse_pos = True
                io.add_mouse_wheel_event(0, -2 if points[key][1] > bottom else 2)
                entered = evidence.frames
                return
            io.mouse_pos = imgui.ImVec2(*points[key])
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
            action, phase, entered = action + 1, 0, evidence.frames

    with controls.patched():
        evidence = run_gui(
            None if restore else root / "source.csv",
            initial_workspace=root / "session.datelier.json" if restore else None,
            smoke_frames=1800,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    screenshot = hello_imgui.final_app_window_screenshot()[:, :, :3]
    output.mkdir(parents=True, exist_ok=True)
    Image.fromarray(screenshot).save(
        output
        / (
            "audio-waveform.png"
            if waveform_only
            else "audio-spectrum-large.png"
            if large_fft
            else "audio-spectrum-restored.png"
            if restore
            else "audio-spectrum.png"
        )
    )
    assert action == len(actions), (action, actions[action:], points, result)
    actual: list[int] = []
    if not waveform_only:
        assert expected_pixel is not None and peak_pixel is not None
        pixel = screenshot[peak_pixel[1], peak_pixel[0], :3].astype(np.int64)
        assert np.max(np.abs(pixel - expected_pixel)) < 48, (
            pixel,
            expected_pixel,
            peak_pixel,
        )
        actual = [int(value) for value in pixel]
    p95 = float(np.percentile(evidence.frame_intervals_ms[10:], 95))
    stage_timings = {
        stage: float(np.percentile(values[2:], 95))
        for stage, values in timings.items()
        if len(values) > 2
    }
    assert p95 < 33, (p95, evidence.frames, result, stage_timings)
    assert "sounddevice" not in sys.modules
    return {
        **result,
        "frames": evidence.frames,
        "frame_p95_ms": p95,
        "raster_frequency_orientation": not waveform_only,
        "peak_pixel": actual,
        "restore": restore,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--restore", type=Path)
    parser.add_argument("--large-fft", action="store_true")
    parser.add_argument("--waveform-only", action="store_true")
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, args.output, True)))
        return
    with TemporaryDirectory(prefix="datelier-audio-spectrum-") as temporary:
        root = Path(temporary)
        source = root / "tones.wav"
        positions = np.arange(16000) / 8000
        samples = np.stack(
            (
                0.5 * np.sin(2 * np.pi * 1000 * positions),
                0.25 * np.cos(2 * np.pi * 2000 * positions),
            ),
            axis=1,
        )
        sf.write(source, samples, 8000, subtype="DOUBLE")
        (root / "source.csv").write_text("id,audio,label\n1,tones.wav,two tones\n")
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        if args.large_fft or args.waveform_only:
            report = run(
                root,
                args.output,
                False,
                large_fft=args.large_fft,
                waveform_only=args.waveform_only,
            )
            assert hashlib.sha256(source.read_bytes()).hexdigest() == before
            report["source_preserved"] = True
            (
                args.output
                / (
                    "audio-waveform-native.json"
                    if args.waveform_only
                    else "audio-spectrum-large-native.json"
                )
            ).write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report))
            return
        saved = run(root, args.output, False)
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
            timeout=60,
        )
        assert completed.returncode == 0, completed.stderr
        assert hashlib.sha256(source.read_bytes()).hexdigest() == before
        report = {
            "save": saved,
            "restore": json.loads(completed.stdout.strip().splitlines()[-1]),
            "source_preserved": True,
        }
        (args.output / "audio-spectrum-native.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
