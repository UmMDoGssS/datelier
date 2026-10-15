"""One editor output owner, source invalidation, independent tabs and record views."""

from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

import numpy as np
import soundfile as sf

from datelier.application.sessions import EditorController, FileController
from datelier.inspection.arrays import ArrayLayout, ArrayRecordMapping
from datelier.inspection.audio.playback.controller import PlaybackPhase
from datelier.inspection.audio.playback.requests import playback_request
from datelier.inspection.audio.types import AudioRange
from datelier.io.types import ArrayOptions
from datelier.pipeline import Sort
from scripts.support.audio_devices import Devices


def loaded(editor: EditorController) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if all(
            not file.loader.status.path or file.loader.active is not None
            for file in editor.files
        ):
            return
        sleep(0.001)
    raise AssertionError(
        [(file.loader.status.path, file.loader.status) for file in editor.files]
    )


def metadata(editor: EditorController, file: FileController, column: str) -> None:
    assert file.loader.active is not None
    options = file.loader.active.imported.options
    file.audio.jobs.request_record(
        file.loader.active.dataset,
        column,
        0,
        file.loader.active.imported.array_catalog,
        options.mapping if isinstance(options, ArrayOptions) else None,
        file.audio.settings.array_sample_rate,
    )
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if file.audio.jobs.metadata is not None:
            return
        sleep(0.001)
    raise AssertionError(file.audio.jobs.message)


def phase(editor: EditorController, expected: PlaybackPhase) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if editor.playback.snapshot.phase == expected:
            return
        sleep(0.001)
    raise AssertionError(editor.playback.snapshot)


def play(file: FileController) -> None:
    assert file.audio.jobs.metadata is not None
    file.audio.play()


def test_shared_player_tab_switch_unrelated_close_and_revision_invalidation(
    tmp_path: Path,
) -> None:
    for name in ("a", "b"):
        sf.write(
            tmp_path / (name + ".wav"),
            np.tile([0.25, -0.5], (10000, 1)),
            8000,
            subtype="DOUBLE",
        )
    devices = Devices()
    editor = EditorController(playback_factory=devices.create)
    try:
        first = editor.new_file(tmp_path / "a.wav")
        second = editor.new_file(tmp_path / "b.wav")
        loaded(editor)
        assert first.audio.player is second.audio.player is editor.playback
        assert editor.playback.snapshot.request is None and not devices.devices
        metadata(editor, first, "path")
        metadata(editor, second, "path")
        editor.activate(first.identity)
        play(first)
        phase(editor, PlaybackPhase.PLAYING)
        editor.activate(second.identity)
        phase(editor, PlaybackPhase.IDLE)
        assert devices.devices[0].closed
        play(second)
        phase(editor, PlaybackPhase.PLAYING)
        editor.close_file(first.identity)
        assert editor.playback.snapshot.phase == PlaybackPhase.PLAYING
        assert not devices.devices[-1].closed
        second.editor.request(Sort(("path",)))
        phase(editor, PlaybackPhase.IDLE)
        assert devices.devices[-1].closed
    finally:
        editor.close()


def test_range_channel_and_rate_changes_stop_only_the_matching_source(
    tmp_path: Path,
) -> None:
    sf.write(
        tmp_path / "signal.wav",
        np.tile([0.25, -0.5], (10000, 1)),
        8000,
        subtype="DOUBLE",
    )
    devices = Devices()
    editor = EditorController(playback_factory=devices.create)
    try:
        file = editor.new_file(tmp_path / "signal.wav")
        loaded(editor)
        metadata(editor, file, "path")
        play(file)
        phase(editor, PlaybackPhase.PLAYING)
        file.audio.settings = replace(file.audio.settings, range=AudioRange(500, 1000))
        phase(editor, PlaybackPhase.IDLE)
        file.audio.settings = replace(
            file.audio.settings,
            playback=replace(file.audio.settings.playback, selected_range=False),
        )
        play(file)
        phase(editor, PlaybackPhase.PLAYING)
        file.audio.settings = replace(
            file.audio.settings, range=AudioRange(600, 1200), channel=1
        )
        editor.poll()
        assert editor.playback.snapshot.phase == PlaybackPhase.PLAYING
        file.audio.settings = replace(
            file.audio.settings,
            playback=replace(file.audio.settings.playback, selected_channel=True),
        )
        phase(editor, PlaybackPhase.IDLE)
        play(file)
        phase(editor, PlaybackPhase.PLAYING)
        assert file.audio.jobs.metadata is not None
        actual = playback_request(file.audio.jobs.metadata, file.audio.settings)
        assert actual.channel == 1 and actual.range == AudioRange(0, 10000)
        editor.close_file(file.identity)
        phase(editor, PlaybackPhase.IDLE)
        assert devices.devices[-1].closed
    finally:
        editor.close()


def test_array_record_view_borrows_output_and_closure_releases_it(
    tmp_path: Path,
) -> None:
    source = tmp_path / "waves.npz"
    np.savez_compressed(source, waves=np.ones((2, 10000, 2), dtype=np.float32))
    devices = Devices()
    editor = EditorController(playback_factory=devices.create)
    try:
        owner = editor.new_file(source)
        loaded(editor)
        mapping = ArrayRecordMapping(
            "waves", layout=ArrayLayout.AUDIO, display_axes=(1,), channel_axis=2
        )
        file = owner.record_views.open_array(owner, mapping)
        deadline = monotonic() + 5
        while file.loader.active is None and monotonic() < deadline:
            editor.poll()
            sleep(0.001)
        assert file.loader.active is not None
        assert file.audio.player is owner.audio.player is editor.playback
        file.audio.settings = replace(file.audio.settings, array_sample_rate=8000)
        metadata(editor, file, "waves")
        play(file)
        phase(editor, PlaybackPhase.PLAYING)
        assert editor.playback.snapshot.request is not None
        assert editor.playback.snapshot.request.locator.origin.file_id == file.identity
        file.records.settings = replace(file.records.settings, focus=1)
        phase(editor, PlaybackPhase.IDLE)
        assert devices.devices[-1].closed
        file.records.settings = replace(file.records.settings, focus=0)
        play(file)
        phase(editor, PlaybackPhase.PLAYING)
        file.audio.settings = replace(file.audio.settings, array_sample_rate=16000)
        phase(editor, PlaybackPhase.IDLE)
        file.audio.settings = replace(file.audio.settings, array_sample_rate=8000)
        play(file)
        phase(editor, PlaybackPhase.PLAYING)
        owner.record_views.close_view(file.identity)
        phase(editor, PlaybackPhase.IDLE)
        assert devices.devices[-1].closed
    finally:
        editor.close()
