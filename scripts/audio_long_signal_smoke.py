"""Native whole-recording and adjacent-range navigation on ten-minute audio."""

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import soundfile as sf
from audio_smoke_controls import NativeControls
from imgui_bundle import hello_imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.inspection.audio.view_types import (
    AudioViewKind,
    SpectralView,
    WaveformEnvelope,
)


def run(source: Path, output: Path) -> dict[str, object]:
    controls = NativeControls()
    actions = [
        "Gallery",
        "Whole recording",
        "Expand",
        "waveform",
        "Restore",
        "Time start (s)=540",
        "Mel spectrogram",
        "Expand",
        "mel",
        "Restore",
        "Earlier range",
        "earlier",
        "Later range",
        "later",
        "Expand",
        "final",
    ]
    action = entered = 0
    started = False
    result: dict[str, object] = {}

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal action, entered, started
        file = editor.active
        if file.loader.active is None:
            return
        params = hello_imgui.get_runner_params()
        if not started:
            file.exploration.tab = "Inspect"
            params.docking_params.focus_dockable_window("Explore")
            started, entered = True, evidence.frames
        if action == len(actions):
            params.app_shall_exit = True
            return
        target, age = actions[action], evidence.frames - entered
        data = file.audio.signal.active
        if target == "waveform":
            if (
                not isinstance(data, WaveformEnvelope)
                or file.audio.signal.busy
                or age < 20
            ):
                return
            assert data.range.start == 0 and data.range.stop == 48000 * 600
            assert np.all(data.minimum == -0.25) and np.all(data.maximum == 0.25)
            assert len(data.times) <= 2048 and len(data.plot_times) == 2
            result.update(whole_frames=48000 * 600, waveform_bytes=data.retained_bytes)
            action, entered = action + 1, evidence.frames
            return
        if target in ("mel", "earlier", "later", "final"):
            if (
                not isinstance(data, SpectralView)
                or data.settings.mode != AudioViewKind.MEL
                or file.audio.signal.busy
                or age < 20
            ):
                return
            start = 480 if target == "earlier" else 540
            assert (
                data.range.start == start * 48000
                and data.range.stop == (start + 60) * 48000
            )
            assert data.metadata.sample_rate == 48000 and data.channel == 0
            assert data.locator.origin.row_id == 0
            assert 1350 < data.frequencies[data.peak[0]] < 1650
            assert start < data.times[0] < start + 1 and data.times[-1] <= start + 60
            assert data.retained_bytes <= file.audio.settings.cpu_bytes
            assert file.audio.canvas.retained_bytes <= file.audio.settings.gpu_bytes
            result[target + "_start_seconds"] = start
            result.update(
                spectral_bytes=data.retained_bytes,
                gpu_bytes=file.audio.canvas.retained_bytes,
                spectral_windows=data.spectral_frames,
                time_step=data.time_step,
            )
            action, entered = action + 1, evidence.frames
            return
        if controls.advance(target, evidence.frames):
            action, entered = action + 1, evidence.frames

    with controls.patched():
        evidence = run_gui(
            source,
            smoke_frames=1600,
            on_editor_frame=frame,
            preferences_path=source.parent / "prefs.json",
        )
    assert action == len(actions), (actions[action:], result, controls.points)
    p95 = float(np.percentile(evidence.frame_intervals_ms[10:], 95))
    assert p95 < 33, (p95, result)
    output.mkdir(parents=True, exist_ok=True)
    screenshot = hello_imgui.final_app_window_screenshot()[:, :, :3]
    Image.fromarray(screenshot).save(output / "audio-long-signal.png")
    return {**result, "frames": evidence.frames, "frame_p95_ms": p95}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="datelier-long-signal-") as temporary:
        path = Path(temporary) / "long.wav"
        rate, frames = 48000, 48000 * 600
        positions = np.arange(65536)
        with sf.SoundFile(
            path, "w", samplerate=rate, channels=2, subtype="FLOAT"
        ) as stream:
            for start in range(0, frames, len(positions)):
                wave = 0.25 * np.sin(2 * np.pi * 1500 * (positions + start) / rate)
                stream.write(
                    np.stack((wave, -wave), axis=1)[: min(len(wave), frames - start)]
                )
        with path.open("rb") as stream:
            original = hashlib.file_digest(stream, "sha256").hexdigest()
        result = run(path, args.output)
        with path.open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == original
        result["source_preserved"] = True
        (args.output / "audio-long-signal-native.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
        print(json.dumps(result))


if __name__ == "__main__":
    main()
