"""Real worker/decoder commands with deterministic devices, output and close gates."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

from datelier.inspection.arrays import ArrayLayout, ArrayRecordMapping
from datelier.inspection.audio.decoding import (
    audio_metadata,
    locate_audio,
    prepare_metadata,
)
from datelier.inspection.audio.playback import PlaybackRequest
from datelier.inspection.audio.playback.controller import AudioPlayback, PlaybackPhase
from datelier.inspection.audio.playback.device import Renderer
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.references import ReferenceSettings
from datelier.io.arrays import ArrayStore
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.records import prepare_array_records
from datelier.io.media import load_media
from scripts.support.audio_devices import Devices, FakeDevice


def gated[**P, T](
    function: Callable[P, T], entered: Event, release: Event
) -> Callable[P, T]:
    def delayed(*args: P.args, **kwargs: P.kwargs) -> T:
        entered.set()
        assert release.wait(5)
        return function(*args, **kwargs)

    return delayed


def wait(player: AudioPlayback, phase: PlaybackPhase) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        state = player.snapshot
        if state.phase == phase:
            return
        sleep(0.001)
    raise AssertionError((phase, player.snapshot))


def request(tmp_path: Path, start: int = 100, stop: int = 10000) -> PlaybackRequest:
    path = tmp_path / "signal.wav"
    sf.write(path, np.tile([0.5, -0.25], (10000, 1)), 8000, subtype="DOUBLE")
    locator, metadata = prepare_metadata(
        load_media(path).dataset, "a", "records", "path", 0, ReferenceSettings(), None
    )
    return PlaybackRequest(locator, metadata, AudioRange(start, stop))


def test_idle_initialization_and_close_never_import_playback_backend() -> None:
    with patch(
        "datelier.inspection.audio.playback.device.import_module",
        side_effect=AssertionError("must stay lazy"),
    ):
        player = AudioPlayback()
        assert player.snapshot.phase == PlaybackPhase.IDLE
        player.close()
        assert player.snapshot.phase == PlaybackPhase.CLOSED


def test_pause_volume_seek_and_scoped_stop_preserve_original_frames(
    tmp_path: Path,
) -> None:
    selected = request(tmp_path)
    original = (tmp_path / "signal.wav").read_bytes()
    devices, store = Devices(), ArrayStore()
    player = AudioPlayback(devices.create)
    try:
        player.play(selected, store, volume=0.5)
        wait(player, PlaybackPhase.PLAYING)
        first = devices.devices[0]
        np.testing.assert_equal(first.pump(), np.tile([0.25, -0.125], (512, 1)))
        assert player.snapshot.position == 612
        player.pause()
        wait(player, PlaybackPhase.PAUSED)
        assert not first.pump().any() and player.snapshot.position == 612
        player.set_volume(0.25)
        player.seek(1500)
        wait(player, PlaybackPhase.PAUSED)
        second = devices.devices[-1]
        assert second is not first and first.closed
        assert not second.pump().any() and player.snapshot.position == 1500
        assert player.snapshot.request is not None
        assert player.snapshot.request.range == selected.range
        player.pause(False)
        np.testing.assert_equal(second.pump(), np.tile([0.125, -0.0625], (512, 1)))
        assert player.snapshot.position == 2012
        player.stop("b")
        assert player.snapshot.phase == PlaybackPhase.PLAYING and not second.closed
        player.stop("a")
        wait(player, PlaybackPhase.IDLE)
        assert second.closed and player.snapshot.position == 2012
        assert player.snapshot.cpu_bytes == 0
        assert (tmp_path / "signal.wav").read_bytes() == original
    finally:
        player.close()
        store.close()


def test_final_partial_block_is_exact_and_does_not_restart(tmp_path: Path) -> None:
    selected = request(tmp_path, 700, 2000)
    devices, store = Devices(), ArrayStore()
    player = AudioPlayback(devices.create)
    try:
        player.play(replace(selected, channel=1), store, volume=1)
        wait(player, PlaybackPhase.PLAYING)
        device = devices.devices[0]
        device.pump()
        device.pump()
        tail = device.pump(1024)
        assert np.all(tail[:276] == -0.25) and not tail[276:].any()
        wait(player, PlaybackPhase.FINISHED)
        assert player.snapshot.position == 2000 and player.snapshot.cpu_bytes == 0
        assert device.closed and len(devices.devices) == 1
        assert player.snapshot.underruns == 0
    finally:
        player.close()
        store.close()


def test_stop_only_acknowledges_after_slow_device_closure(tmp_path: Path) -> None:
    selected = request(tmp_path)
    devices, store = Devices(), ArrayStore()
    player = AudioPlayback(devices.create)
    gate = Event()
    try:
        player.play(selected, store)
        wait(player, PlaybackPhase.PLAYING)
        device = devices.devices[0]
        device.close_gate = gate
        player.stop()
        assert device.closing.wait(5)
        assert player.snapshot.phase == PlaybackPhase.STOPPING and not device.closed
        player.close(wait=False)
        assert player.snapshot.phase == PlaybackPhase.STOPPING
        gate.set()
        player.close()
        assert player.snapshot.phase == PlaybackPhase.CLOSED and device.closed
    finally:
        gate.set()
        player.close()
        store.close()


def test_latest_source_coalesces_while_device_opening_and_closes_before_replace(
    tmp_path: Path,
) -> None:
    selected = request(tmp_path)
    devices, store = Devices(), ArrayStore()
    entered, release = Event(), Event()

    def create(chosen: PlaybackRequest, render: Renderer) -> FakeDevice:
        device = devices.create(chosen, render)
        if len(devices.devices) == 1:
            entered.set()
            assert release.wait(5)
        return device

    player = AudioPlayback(create)
    try:
        player.play(selected, store)
        assert entered.wait(5)
        for index in range(20):
            locator = replace(
                selected.locator,
                origin=replace(selected.locator.origin, file_id=f"f{index}"),
            )
            player.play(
                replace(selected, locator=locator, start_frame=1000 + index), store
            )
        release.set()
        wait(player, PlaybackPhase.PLAYING)
        assert len(devices.devices) == 2 and devices.devices[0].closed
        assert player.snapshot.request is not None
        assert player.snapshot.request.locator.origin.file_id == "f19"
        assert player.snapshot.position == 1019
        player.stop("a")
        assert player.snapshot.phase == PlaybackPhase.PLAYING
    finally:
        release.set()
        player.close()
        store.close()


@pytest.mark.parametrize("failure", ["open", "start", "disconnect", "close"])
def test_device_failures_are_visible_and_buffers_retire(
    tmp_path: Path, failure: str
) -> None:
    selected = request(tmp_path)
    devices, store = Devices(), ArrayStore()

    def create(chosen: PlaybackRequest, render: Renderer) -> FakeDevice:
        if failure == "open":
            raise RuntimeError("Output device unavailable")
        device = devices.create(chosen, render)
        if failure == "start":
            device.start_error = "Output start failed"
        return device

    player = AudioPlayback(create)
    try:
        player.play(selected, store)
        if failure in ("disconnect", "close"):
            wait(player, PlaybackPhase.PLAYING)
            device = devices.devices[0]
            if failure == "close":
                device.close_error = "Closure unconfirmed"
                player.stop()
            else:
                device.active = False
        wait(player, PlaybackPhase.FAILED)
        assert "failed" in player.snapshot.message.lower()
        assert player.snapshot.cpu_bytes == 0
        assert all(device.closed for device in devices.devices)
    finally:
        player.close()
        store.close()


def test_close_during_source_read_prevents_start_and_source_publication(
    tmp_path: Path,
) -> None:
    selected = request(tmp_path)
    devices, store = Devices(), ArrayStore()
    entered, release = Event(), Event()
    player = AudioPlayback(devices.create)
    try:
        with patch.object(
            sf.SoundFile, "read", gated(sf.SoundFile.read, entered, release)
        ):
            player.play(selected, store)
            assert entered.wait(5)
            player.close(wait=False)
            assert player.snapshot.phase == PlaybackPhase.STOPPING
            release.set()
            player.close()
        assert player.snapshot.phase == PlaybackPhase.CLOSED
        assert len(devices.devices) == 1 and devices.devices[0].closed
        with pytest.raises(RuntimeError, match="closed"):
            player.play(selected, store)
    finally:
        release.set()
        player.close()
        store.close()


def test_compressed_record_has_one_lease_and_stop_releases_oversized_data(
    tmp_path: Path,
) -> None:
    path = tmp_path / "waves.npz"
    values = np.zeros((2, 10000, 2), dtype=np.float32)
    values[1] = [0.25, -0.5]
    np.savez_compressed(path, waves=values)
    original = path.read_bytes()
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping(
        "waves", layout=ArrayLayout.AUDIO, display_axes=(1,), channel_axis=2
    )
    store = ArrayStore(retained_bytes=1, directory=tmp_path)
    devices, player = Devices(), None
    try:
        dataset, _ = prepare_array_records(store, catalog, mapping)
        locator = locate_audio(
            dataset,
            "array",
            "waves",
            "waves",
            1,
            ReferenceSettings(),
            None,
            catalog,
            mapping,
        )
        selected = PlaybackRequest(
            locator, audio_metadata(locator, 8000), AudioRange(600, 5000), channel=1
        )
        player = AudioPlayback(devices.create)
        player.play(selected, store, volume=1)
        wait(player, PlaybackPhase.PLAYING)
        assert store.extractions == 1 and store.stored_bytes > 1
        np.testing.assert_equal(devices.devices[0].pump(), np.full((512, 1), -0.5))
        assert player.snapshot.position == 1112
        player.stop()
        wait(player, PlaybackPhase.IDLE)
        assert store.stored_bytes == 0 and devices.devices[0].closed
        temporary = store.temporary_path
        player.close()
        store.close()
        assert temporary is not None and not temporary.exists()
        assert path.read_bytes() == original
    finally:
        if player is not None:
            player.close()
        store.close()


def test_changed_source_stops_device_and_does_not_publish_obsolete_samples(
    tmp_path: Path,
) -> None:
    selected = request(tmp_path)
    path = tmp_path / "signal.wav"
    devices, store = Devices(), ArrayStore()
    player = AudioPlayback(devices.create)
    try:
        player.play(selected, store)
        wait(player, PlaybackPhase.PLAYING)
        path.write_bytes(path.read_bytes() + b"changed")
        devices.devices[0].pump()
        wait(player, PlaybackPhase.FAILED)
        assert "changed" in player.snapshot.message.lower()
        assert devices.devices[0].closed and player.snapshot.cpu_bytes == 0
        player.stop()
        assert "changed" in player.snapshot.message.lower()
    finally:
        player.close()
        store.close()
