"""Native file/mapped-array mel recipes, original record identity and idle restore."""

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
from datelier.inspection.audio.mel import mel_filters
from datelier.inspection.audio.view_types import (
    AudioViewKind,
    AudioWindow,
    SpectralView,
)
from datelier.pipeline.operations import Sort


def run(root: Path, output: Path, *, restore: bool, array: bool) -> dict[str, object]:
    controls = NativeControls()
    actions = (
        [
            *(("Prepare saved array records",) if array else ()),
            "Expand",
            "hover",
            "restored",
        ]
        if restore
        else [
            "Gallery",
            *(("Array sample rate (Hz; 0 = unknown)=8000",) if array else ()),
            "Time start (s)=0.5",
            "Time end (s)=1.5",
            "Sample channel (1-based)=2",
            "Mel spectrogram",
            "Signal settings",
            "Signal FFT length=512",
            "Signal hop length=128",
            "Hamming",
            "Mel bands (HTK)=32",
            "Minimum frequency (Hz)=500",
            "Maximum frequency (Hz; 0 = Nyquist)=3000",
            "Linear band power",
            "Decibels",
            "Decibel floor=-80",
            "Audio memory (MiB)=4",
            "Audio texture memory (MiB)=1",
            "Signal settings",
            "Expand",
            "hover",
            "save",
        ]
    )
    stage = action = entered = hover_phase = 0
    started = False
    report: dict[str, object] = {}
    expected_color: tuple[int, int, int, int] | None = None
    peak_pixel: tuple[int, int] | None = None

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal \
            stage, \
            action, \
            entered, \
            hover_phase, \
            started, \
            expected_color, \
            peak_pixel
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
        data = file.audio.signal.active
        if target == "hover":
            point = file.audio.canvas.peak_pixel
            if (
                not isinstance(data, SpectralView)
                or data.settings.mode != AudioViewKind.MEL
                or point is None
                or age < 15
            ):
                return
            if hover_phase == 0:
                io.mouse_pos = imgui.ImVec2(*point)
                io.want_set_mouse_pos = True
                hover_phase, entered = 1, evidence.frames
            elif age > 12 and file.audio.canvas.readout is not None:
                reading = file.audio.canvas.readout
                band, _ = data.peak
                bank = mel_filters(8000, 512, 32, 500, 3000)
                tone = 2500 if array else 2000
                assert bank.edges[band] < tone < bank.edges[band + 2]
                assert reading[1] == data.frequencies[band] and reading[2] > 0
                expected_color = data.color_pixel(*data.peak)
                peak_pixel = round(point[0]), round(point[1])
                report.update(
                    band_center_hz=reading[1],
                    source_tone_hz=tone,
                    band_power=reading[2],
                )
                action, entered = action + 1, evidence.frames
            return
        if target in ("save", "restored"):
            if not isinstance(data, SpectralView) or file.audio.signal.busy or age < 15:
                return
            settings = file.audio.settings
            assert (
                settings.view.mode == AudioViewKind.MEL
                and settings.view.mel_bands == 32
            )
            assert (
                settings.view.fft == 512
                and settings.view.hop == 128
                and settings.view.window == AudioWindow.HAMMING
            )
            assert (
                settings.view.frequency_low == 500
                and settings.view.frequency_high == 3000
                and settings.view.db_floor == -80
            )
            assert (
                settings.range.start == 4000
                and settings.range.stop == 12000
                and settings.channel == 1
            )
            assert settings.cpu_bytes == 4 * 1024**2 and settings.gpu_bytes == 1024**2
            assert data.locator.origin.row_id == (1 if array else 0)
            assert data.metadata.sample_rate == 8000 and data.metadata.channels == 2
            assert file.audio.jobs.active is file.audio.jobs.profile is None
            if array:
                assert file.loader.active is not None
                assert file.loader.active.dataset.table["label"][0] == 1
            report.update(
                source_row=data.locator.origin.row_id,
                cpu_bytes=data.retained_bytes,
                gpu_bytes=file.audio.canvas.retained_bytes,
                empty_bands=data.mel_empty_bands,
                original_sample_rate=8000,
                supporting_label=1 if array else "two tones",
                profiles_and_samples_idle=True,
            )
            assert data.retained_bytes <= settings.cpu_bytes
            assert file.audio.canvas.retained_bytes <= settings.gpu_bytes
            if not restore:
                editor.save_workspace(
                    root / "session.datelier.json",
                    layout=imgui.save_ini_settings_to_memory(),
                )
            action, entered = action + 1, evidence.frames
            return
        if controls.advance(target, evidence.frames):
            action, entered = action + 1, evidence.frames

    with controls.patched():
        evidence = run_gui(
            None if restore else root / ("waves.npz" if array else "source.csv"),
            initial_workspace=root / "session.datelier.json" if restore else None,
            smoke_frames=1800,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    assert action == len(actions), (action, actions[action:], report, controls.points)
    assert expected_color is not None and peak_pixel is not None
    screenshot = hello_imgui.final_app_window_screenshot()[:, :, :3]
    name = "audio-mel-array" if array else "audio-mel-file"
    output.mkdir(parents=True, exist_ok=True)
    Image.fromarray(screenshot).save(
        output / (name + ("-restored.png" if restore else ".png"))
    )
    actual = screenshot[peak_pixel[1], peak_pixel[0], :3].astype(np.int64)
    assert np.max(np.abs(actual - expected_color[:3])) < 48, (
        actual,
        expected_color,
        peak_pixel,
    )
    p95 = float(np.percentile(evidence.frame_intervals_ms[10:], 95))
    assert p95 < 33, (p95, report)
    assert "sounddevice" not in sys.modules
    return {
        **report,
        "restore": restore,
        "frames": evidence.frames,
        "frame_p95_ms": p95,
        "mel_raster_orientation": True,
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
    with TemporaryDirectory(prefix="datelier-audio-mel-") as temporary:
        root = Path(temporary)
        positions = np.arange(16000) / 8000
        if args.array:
            waves = np.empty((3, 16000, 2), dtype=np.float32)
            for row in range(3):
                waves[row, :, 0] = 0.25 * np.sin(
                    2 * np.pi * (1000 + 250 * row) * positions
                )
                waves[row, :, 1] = (
                    0.25
                    * (row + 1)
                    * np.cos(2 * np.pi * (2000 + 500 * row) * positions)
                )
            source = root / "waves.npz"
            np.savez_compressed(source, waves=waves, labels=np.array([3, 1, 2]))
        else:
            source = root / "tones.wav"
            sf.write(
                source,
                np.stack(
                    (
                        0.5 * np.sin(2 * np.pi * 1000 * positions),
                        0.25 * np.cos(2 * np.pi * 2000 * positions),
                    ),
                    axis=1,
                ),
                8000,
                subtype="DOUBLE",
            )
            (root / "source.csv").write_text("id,audio,label\n1,tones.wav,two tones\n")
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
                "audio-mel-array-native.json"
                if args.array
                else "audio-mel-file-native.json"
            )
        ).write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
