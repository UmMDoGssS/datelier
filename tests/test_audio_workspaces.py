"""Independent audio recipes restore without decoded or profiled signals."""

from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

import numpy as np
import pytest
import soundfile as sf

from datelier.application.editor import EditorController
from datelier.application.workspace import capture_session
from datelier.core.column_roles import ColumnRole
from datelier.inspection.audio.playback.settings import PlaybackSettings
from datelier.inspection.audio.profile_types import AudioThresholds
from datelier.inspection.audio.settings import AudioSettings
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.audio.view_types import (
    AudioViewKind,
    AudioWindow,
    SignalViewSettings,
    SpectrumScale,
)
from datelier.inspection.heatmaps import Colormap
from datelier.workspace.recipes.codec import decode_record, encode
from datelier.workspace.sessions.jobs import save_snapshot
from datelier.workspace.single import WorkspaceViews


def wait(editor: EditorController) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if not editor.workspace.busy and all(
            (not file.loader.status.path or file.loader.active is not None)
            and not file.references.busy
            and not file.audio.jobs.busy
            and not file.audio.signal.busy
            for file in editor.all_files
        ):
            return
        sleep(0.001)
    raise AssertionError("Audio session work did not finish")


def test_audio_settings_and_legacy_workspace_defaults() -> None:
    settings = AudioSettings(
        22050, AudioRange(200, 300), AudioThresholds(0.75, 0.01), 1, 1024 * 1024
    )
    settings.validate()
    settings = replace(
        settings,
        view=SignalViewSettings(
            mode=AudioViewKind.SPECTROGRAM,
            fft=512,
            hop=128,
            window=AudioWindow.HAMMING,
            frequency_low=500,
            frequency_high=3000,
            scale=SpectrumScale.POWER,
            time_bins=16,
            frequency_bins=64,
            colormap=Colormap.PURPLE_GOLD,
            color_range=(0, 1),
        ),
        gpu_bytes=1024**2,
        plot_height=300,
        playback=PlaybackSettings(0.25, False, True, "saved output, ALSA", 250),
    )
    views = replace(WorkspaceViews(), audio=settings)
    assert decode_record(WorkspaceViews, encode(views)) == views
    legacy = encode(WorkspaceViews())
    assert isinstance(legacy, dict)
    del legacy["audio"]
    assert decode_record(WorkspaceViews, legacy).audio == AudioSettings()
    legacy_audio = encode(AudioSettings())
    assert isinstance(legacy_audio, dict)
    for name in ("view", "gpu_bytes", "plot_height", "playback"):
        del legacy_audio[name]
    assert decode_record(AudioSettings, legacy_audio) == AudioSettings()
    legacy_signal = encode(SignalViewSettings(mode=AudioViewKind.SPECTROGRAM))
    assert isinstance(legacy_signal, dict)
    del legacy_signal["mel_bands"]
    assert decode_record(SignalViewSettings, legacy_signal).mel_bands == 64
    for invalid in (
        replace(settings, array_sample_rate=0),
        replace(settings, playback=PlaybackSettings(volume=float("nan"))),
        replace(settings, playback=PlaybackSettings(volume=1.01)),
        replace(settings, playback=PlaybackSettings(seek_frame=-1)),
        replace(settings, playback=PlaybackSettings(device="")),
        replace(settings, view=replace(settings.view, mel_bands=0)),
        replace(settings, view=replace(settings.view, mel_bands=513)),
        replace(settings, channel=-1),
        replace(settings, cpu_bytes=0),
        replace(settings, range=AudioRange(4, 1)),
    ):
        with pytest.raises(ValueError):
            invalid.validate()


def test_two_audio_recipes_restore_idle_with_independent_source_ids(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "session.datelier.json"
    editor = EditorController()
    expected = []
    try:
        for i, name in enumerate(("a", "b")):
            path = tmp_path / (name + ".wav")
            sf.write(path, np.full((100, 2), 0.25 + i * 0.25), 8000, subtype="DOUBLE")
            file = editor.new_file(path)
            expected.append(
                replace(
                    AudioSettings(),
                    range=AudioRange(10, 50),
                    thresholds=AudioThresholds(0.8, 0.01),
                    channel=i,
                    playback=PlaybackSettings(0.25, bool(i), bool(i), None, 10),
                    view=SignalViewSettings(
                        fft=512,
                        hop=128,
                        frequency_high=3000,
                        mel_bands=32,
                        mode=AudioViewKind.MEL if i else AudioViewKind.SPECTROGRAM,
                    ),
                )
            )
        wait(editor)
        files = [file for file in editor.all_files if file.loader.active is not None]
        assert len(files) == 2
        for file, settings in zip(files, expected, strict=True):
            assert file.loader.active is not None
            dataset = file.loader.active.dataset
            assert dataset.role("path").role == ColumnRole.AUDIO
            file.audio.settings = settings
            file.audio.sync(file.media_input())
            file.audio.jobs.request_record(dataset, "path", 0)
        wait(editor)
        for file in files:
            assert file.audio.jobs.active is file.audio.jobs.profile is None
            file.audio.jobs.request_profile(
                AudioRange(), file.audio.settings.thresholds, file.arrays.store
            )
            assert file.audio.jobs.metadata is not None
            file.audio.signal.bind(file.audio.jobs.metadata)
            file.audio.signal.request(
                AudioRange(10, 50),
                file.audio.settings.channel,
                file.audio.settings.view,
                file.arrays.store,
                file.audio.settings.cpu_bytes,
            )
        wait(editor)
        profiles = [file.audio.jobs.profile for file in files]
        assert profiles[0] is not None and profiles[1] is not None
        assert (
            profiles[0].locator.origin.row_id == profiles[1].locator.origin.row_id == 0
        )
        assert profiles[0].locator.origin.file_id != profiles[1].locator.origin.file_id
        save_snapshot(workspace, capture_session(editor), False)
        text = workspace.read_text()
        assert "AudioSignalProfile" not in text and "PreparedAudio" not in text
        assert "SpectralView" not in text and "WaveformEnvelope" not in text
        assert "PlaybackSnapshot" not in text and "PlaybackRun" not in text
    finally:
        editor.close()
    restored = EditorController()
    try:
        restored.open_workspace(workspace)
        wait(restored)
        files = [file for file in restored.all_files if file.loader.active is not None]
        assert len(files) == 2
        assert [file.audio.settings for file in files] == expected
        for file in files:
            assert (
                file.audio.jobs.active
                is file.audio.jobs.profile
                is file.audio.jobs.metadata
                is None
            )
            assert not file.audio.jobs.busy and file.arrays.store.temporary_path is None
            assert file.audio.signal.active is None and not file.audio.signal.busy
            assert file.audio.player.snapshot.request is None
            assert not file.audio.player.devices.busy
    finally:
        restored.close()
