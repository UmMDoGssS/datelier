"""Native spectral/collection/listening commands with deterministic output injection."""

import json
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import soundfile as sf
from imgui_bundle import hello_imgui, imgui

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.audio.playback.controller import PlaybackPhase
from datelier.inspection.audio.signal import AudioViewKind, SpectralView
from datelier.inspection.audio.types import AudioRange

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from audio_playback_fixtures import Devices  # noqa: E402


def main() -> None:
    with TemporaryDirectory(prefix="datelier-rebuild-audio-") as directory:
        root = Path(directory)
        source = root / "signal.wav"
        signal = np.sin(2 * np.pi * 440 * np.arange(32000) / 8000)
        sf.write(source, signal, 8000, subtype="DOUBLE")
        original = source.read_bytes()
        devices = Devices()
        stage, entered, click_stage, next_stage = 0, 0, 0, 0
        clicking: tuple[float, float] | None = None
        done = False

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, click_stage, next_stage, clicking, done
            file, io = editor.current, imgui.get_io()
            age = evidence.frames - entered
            if evidence.frames > 800:
                raise AssertionError(
                    (
                        stage,
                        file.audio.jobs.message,
                        file.audio.signal.message,
                        editor.playback.snapshot,
                    )
                )
            if clicking:
                io.mouse_pos = imgui.ImVec2(*clicking)
                io.want_set_mouse_pos = True
                if age < 4:
                    return
                if click_stage == 0:
                    io.add_mouse_button_event(0, True)
                    click_stage, entered = 1, evidence.frames
                elif click_stage == 1:
                    io.add_mouse_button_event(0, False)
                    click_stage, entered = 2, evidence.frames
                else:
                    clicking = None
                    stage, entered = next_stage, evidence.frames
                return
            suffix: tuple[str, ...] | None = None
            if stage == 0 and file.inspection:
                file.records.settings = replace(
                    file.records.settings, primary="path", gallery=False
                )
                editor.choose_route("Inspect")
                stage, entered = 1, evidence.frames
            elif stage == 1 and file.audio.jobs.metadata:
                assert (
                    file.audio.signal.active is None and file.audio.jobs.active is None
                )
                assert not devices.devices and editor.playback.snapshot.request is None
                file.audio.settings = replace(
                    file.audio.settings,
                    range=AudioRange(0, 32000),
                    view=replace(
                        file.audio.settings.view,
                        mode=AudioViewKind.SPECTROGRAM,
                        fft=512,
                        hop=128,
                        time_bins=256,
                        frequency_bins=256,
                    ),
                )
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 5:
                suffix, next_stage = ("commands", "waveform", "run"), 3
            elif stage == 3 and isinstance(file.audio.signal.active, SpectralView):
                view = file.audio.signal.active
                assert (
                    view.metadata.sample_rate == 8000
                    and abs(view.frequencies[view.peak[0]] - 440) < 20
                )
                file.audio.settings = replace(
                    file.audio.settings,
                    view=replace(
                        file.audio.settings.view, mode=AudioViewKind.MEL, mel_bands=32
                    ),
                )
                stage, entered = 4, evidence.frames
            elif stage == 4 and age > 5:
                suffix, next_stage = ("commands", "waveform", "run"), 5
            elif (
                stage == 5
                and isinstance(file.audio.signal.active, SpectralView)
                and file.audio.signal.active.settings.mode == AudioViewKind.MEL
            ):
                point = next(
                    (
                        point
                        for key, point in probe.targets.items()
                        if key.path[-2:] == ("listening", "toggle")
                    ),
                    None,
                )
                if point and point[1] < 540:
                    suffix, next_stage = ("listening", "toggle"), 6
                else:
                    scroll = next(
                        point
                        for key, point in probe.targets.items()
                        if key.path[-2:] == ("canvas", "scroll")
                    )
                    io.mouse_pos = imgui.ImVec2(*scroll)
                    io.want_set_mouse_pos = True
                    if age % 5 == 0:
                        io.add_mouse_wheel_event(0, -2)
            elif stage == 6 and age > 5:
                suffix, next_stage = ("playback", "play", "run"), 7
            elif stage == 7 and editor.playback.snapshot.phase == PlaybackPhase.PLAYING:
                assert devices.devices[0].request.metadata.sample_rate == 8000
                np.testing.assert_allclose(
                    devices.devices[0].pump(256)[:, 0], signal[:256] * 0.5, atol=1e-7
                )
                suffix, next_stage = ("playback", "pause", "run"), 8
            elif stage == 8 and editor.playback.snapshot.phase == PlaybackPhase.PAUSED:
                suffix, next_stage = ("playback", "stop", "run"), 9
            elif stage == 9 and editor.playback.snapshot.phase == PlaybackPhase.IDLE:
                assert all(device.closed for device in devices.devices)
                file.profiles.choose(("path",))
                editor.choose_route("Profiles")
                stage, entered = 10, evidence.frames
            elif stage == 10 and age > 5:
                suffix, next_stage = ("audio-profile-settings", "prepare", "run"), 11
            elif stage == 11 and file.audio.collection.active:
                assert (
                    file.audio.collection.active.ready == 1
                    and file.audio.collection.active.records["frames"][0] == 32000
                )
                assert source.read_bytes() == original
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix:
                point = next(
                    (
                        point
                        for key, point in probe.targets.items()
                        if key.path[-len(suffix) :] == suffix
                    ),
                    None,
                )
                if point:
                    if not 70 < point[1] < 540:
                        panel = "context" if point[0] > 1000 else "canvas"
                        scroll = next(
                            point
                            for key, point in probe.targets.items()
                            if key.path[-2:] == (panel, "scroll")
                        )
                        io.mouse_pos = imgui.ImVec2(*scroll)
                        io.want_set_mouse_pos = True
                        if age % 5 == 0:
                            io.add_mouse_wheel_event(0, -1 if point[1] >= 540 else 1)
                        return
                    io.mouse_pos = imgui.ImVec2(*point)
                    io.want_set_mouse_pos = True
                    clicking, click_stage, entered = point, 0, evidence.frames

        evidence = run_gui(
            initial_path=source, on_probe_frame=frame, playback_factory=devices.create
        )
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_psd_mel": True,
            "native_header_collection": True,
            "native_explicit_play_pause_stop": True,
            "original_rate_signal": True,
            "source_preserved": True,
            "output_devices_closed": all(device.closed for device in devices.devices),
            "human_listening": "deferred",
        }
        Path("/tmp/datelier-rebuild-audio.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
