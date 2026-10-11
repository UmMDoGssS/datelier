"""Explicit collection/spectrum/listening commands and independent source ownership."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

import numpy as np
import soundfile as sf
from audio_playback_fixtures import Devices

from datelier.application.sessions import EditorController
from datelier.inspection.audio.collections.settings import AudioProfileMode
from datelier.inspection.audio.playback.controller import PlaybackPhase
from datelier.inspection.audio.signal import AudioViewKind, SpectralView
from datelier.inspection.audio.types import AudioRange


def until(editor: EditorController, condition: Callable[[], bool]) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if condition():
            return
        sleep(0.001)
    raise AssertionError(
        (
            editor.active.audio.jobs.message,
            editor.active.audio.collection.message,
            editor.active.audio.signal.message,
        )
    )


def test_explicit_headers_signal_samples_and_collection_keep_original_values(
    tmp_path: Path,
) -> None:
    path = tmp_path / "signal.wav"
    values = np.sin(2 * np.pi * 440 * np.arange(8000) / 8000)
    sf.write(path, values, 8000, subtype="DOUBLE")
    original = path.read_bytes()
    editor = EditorController()
    try:
        file = editor.active
        file.open(path)
        until(editor, lambda: file.inspection is not None)
        assert file.audio.collection.active is None and file.audio.signal.active is None
        file.audio.request_collection("path")
        until(editor, lambda: file.audio.collection.active is not None)
        headers = file.audio.collection.active
        assert headers and headers.ready == 1 and headers.records["frames"][0] == 8000
        assert file.audio.jobs.metadata is None and file.audio.jobs.active is None
        file.audio.request_record("path", 0)
        until(editor, lambda: file.audio.jobs.metadata is not None)
        file.audio.settings = replace(
            file.audio.settings,
            range=AudioRange(0, 8000),
            view=replace(
                file.audio.settings.view,
                mode=AudioViewKind.SPECTROGRAM,
                fft=512,
                hop=128,
            ),
        )
        file.audio.request_signal()
        until(editor, lambda: file.audio.signal.active is not None)
        view = file.audio.signal.active
        assert isinstance(view, SpectralView) and view.metadata.sample_rate == 8000
        assert abs(view.frequencies[view.peak[0]] - 440) < 20
        file.audio.settings = replace(file.audio.settings, range=AudioRange(10, 20))
        file.audio.request_samples()
        until(editor, lambda: file.audio.jobs.active is not None)
        assert file.audio.jobs.active
        np.testing.assert_array_equal(file.audio.jobs.active.raw[:, 0], values[10:20])
        file.audio.settings = replace(
            file.audio.settings,
            collection=replace(
                file.audio.settings.collection, mode=AudioProfileMode.SIGNAL
            ),
        )
        file.audio.request_collection("path")
        until(editor, lambda: file.audio.collection.active is not None)
        assert (
            file.audio.collection.active
            and file.audio.collection.active.channel_records.height == 1
        )
        assert (
            editor.playback.snapshot.request is None and path.read_bytes() == original
        )
    finally:
        editor.close()


def test_shared_output_injection_and_view_switch_release_original_stream(
    tmp_path: Path,
) -> None:
    path = tmp_path / "signal.wav"
    sf.write(path, np.tile([0.25, -0.5], (10000, 1)), 8000, subtype="DOUBLE")
    original = path.read_bytes()
    devices = Devices()
    editor = EditorController(playback_factory=devices.create)
    try:
        first = editor.active
        first.open(path)
        until(editor, lambda: first.inspection is not None)
        first.audio.request_record("path", 0)
        until(editor, lambda: first.audio.jobs.metadata is not None)
        first.audio.settings = replace(first.audio.settings, range=AudioRange(0, 10000))
        first.audio.play()
        until(editor, lambda: editor.playback.snapshot.phase == PlaybackPhase.PLAYING)
        output = devices.devices[0].pump(512)
        np.testing.assert_allclose(output, np.tile([0.125, -0.25], (512, 1)))
        first.audio.pause()
        assert editor.playback.snapshot.phase == PlaybackPhase.PAUSED
        first.audio.seek(400)
        until(
            editor,
            lambda: (
                len(devices.devices) == 2
                and editor.playback.snapshot.phase == PlaybackPhase.PAUSED
            ),
        )
        editor.new_file()
        until(editor, lambda: editor.playback.snapshot.phase == PlaybackPhase.IDLE)
        assert all(device.closed for device in devices.devices)
        assert path.read_bytes() == original
    finally:
        editor.close()


def test_confirmed_payload_survives_removing_display_identity_column(
    tmp_path: Path,
) -> None:
    from datelier.application.media.records import RecordKind
    from datelier.inspection.arrays import (
        ArrayLayout,
        ArrayRecordMapping,
        SupportingArray,
    )
    from datelier.pipeline import SelectColumns, Sort

    source = tmp_path / "waves.npz"
    values = np.arange(24, dtype=np.float32).reshape(3, 8)
    np.savez_compressed(
        source, waves=values, labels=np.array([3, 1, 2]), wrong=np.arange(2)
    )
    editor = EditorController()
    try:
        owner = editor.active
        owner.open(source)
        until(editor, lambda: owner.inspection is not None)
        mapping = ArrayRecordMapping(
            "waves",
            layout=ArrayLayout.AUDIO,
            display_axes=(1,),
            supporting=(SupportingArray("labels", "label"),),
        )
        view = owner.record_views.open_array(owner, mapping)
        until(editor, lambda: view.inspection is not None)
        view.editor.request(Sort(("label",)))
        until(editor, lambda: not view.editor.busy)
        view.editor.request(SelectColumns(("label",)))
        until(editor, lambda: not view.editor.busy)
        assert view.inspection and view.inspection.dataset.row_ids.to_list() == [
            1,
            2,
            0,
        ]
        assert view.records.current_kind() == RecordKind.AUDIO
        view.records.jobs.get(0)
        until(editor, lambda: view.records.jobs.get(0) is not None)
        page = view.records.jobs.get(0)
        assert page
        card = view.records.presentation(page.cards[0])
        assert card.primary and card.primary.name == "waves" and card.row_id == 1
        view.audio.settings = replace(view.audio.settings, array_sample_rate=8000)
        view.audio.request_record(card.primary.name, card.position)
        until(editor, lambda: view.audio.jobs.metadata is not None)
        assert (
            view.audio.jobs.metadata and view.audio.jobs.metadata[0].source_index == 1
        )
        view.records.settings = replace(view.records.settings, mapped_payload=False)
        assert view.records.current_kind() == RecordKind.VALUE
        assert view.records.presentation(page.cards[0]) is page.cards[0]
    finally:
        editor.close()
