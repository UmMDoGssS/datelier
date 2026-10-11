"""Muted physical output: bounded long-file/array buffers, seek and release budgets."""

import argparse
import hashlib
import json
import resource
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter, sleep

import numpy as np
import soundfile as sf
from audio_playback_smoke import wait

from datelier.inspection.arrays import ArrayLayout, ArrayRecordMapping
from datelier.inspection.audio.decoding import prepare_metadata
from datelier.inspection.audio.playback import PlaybackRequest
from datelier.inspection.audio.playback.controller import AudioPlayback, PlaybackPhase
from datelier.inspection.audio.playback.device import Renderer, SoundDeviceOutput
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.references import ReferenceSettings
from datelier.io.arrays import ArrayStore
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.records import prepare_array_records
from datelier.io.media import load_media


class ObservedOutput(SoundDeviceOutput):
    def __init__(self, request: PlaybackRequest, render: Renderer) -> None:
        self.closed = False
        started = perf_counter()
        import_module("sounddevice")
        self.import_seconds = perf_counter() - started
        started = perf_counter()
        super().__init__(request, render)
        self.open_seconds = perf_counter() - started

    def close(self) -> None:
        super().close()
        self.closed = True


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def exercise(
    player: AudioPlayback,
    request: PlaybackRequest,
    store: ArrayStore,
    devices: list[ObservedOutput],
    startup_limit: float,
) -> dict[str, object]:
    initial_devices = len(devices)
    started = perf_counter()
    player.play(request, store, volume=0)
    state = wait(
        player,
        lambda s: s.phase == PlaybackPhase.PLAYING and s.position > request.first_frame,
    )
    startup = perf_counter() - started
    assert startup < startup_limit and state.cpu_bytes <= 1024**2, (
        startup,
        devices[-1].import_seconds,
        devices[-1].open_seconds,
    )
    device, latency, retained = state.device, state.latency, state.cpu_bytes
    player.pause()
    started = perf_counter()
    sleep(0.05)
    position = player.snapshot.position
    sleep(0.05)
    assert (
        player.snapshot.phase == PlaybackPhase.PAUSED
        and player.snapshot.position == position
    )
    pause = perf_counter() - started
    assert pause < 0.3
    first, last = request.range.bounds(request.metadata.frames)
    seek_frame = first + (last - first) * 3 // 4
    started = perf_counter()
    player.seek(seek_frame)
    seeked = wait(
        player,
        lambda s: (
            s.phase == PlaybackPhase.PAUSED
            and s.request is not None
            and s.request.first_frame == seek_frame
        ),
    )
    seek = perf_counter() - started
    assert seek < 0.3 and seeked.position == seek_frame
    assert devices[initial_devices].closed
    player.pause(False)
    wait(player, lambda s: s.phase == PlaybackPhase.PLAYING and s.position > seek_frame)
    started = perf_counter()
    player.stop()
    stopped = wait(player, lambda s: s.phase == PlaybackPhase.IDLE)
    stop = perf_counter() - started
    assert stop < 0.3 and stopped.cpu_bytes == 0
    assert all(d.closed for d in devices[initial_devices:])
    assert stopped.request is not None
    assert stopped.request.locator.origin == request.locator.origin
    assert stopped.request.metadata.sample_rate == request.metadata.sample_rate
    return {
        "startup_seconds": startup,
        "startup_limit_seconds": startup_limit,
        "pause_stable_seconds": pause,
        "seek_seconds": seek,
        "stop_closed_seconds": stop,
        "device": device,
        "reported_latency_seconds": latency,
        "retained_output_bytes": retained,
        "retained_after_stop": stopped.cpu_bytes,
        "original_rate": request.metadata.sample_rate,
        "channels": request.channels,
        "source_row": request.locator.origin.row_id,
        "seek_frame": seek_frame,
        "underruns": stopped.underruns,
        "devices_closed": True,
        "sdk_import_seconds": devices[initial_devices].import_seconds,
        "device_open_seconds": devices[initial_devices].open_seconds,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="Default Sink, PulseAudio")
    args = parser.parse_args()
    baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    devices: list[ObservedOutput] = []

    def output(request: PlaybackRequest, render: Renderer) -> ObservedOutput:
        device = ObservedOutput(request, render)
        devices.append(device)
        return device

    player = AudioPlayback(output)
    with TemporaryDirectory(prefix="datelier-playback-resource-") as temporary:
        root = Path(temporary)
        path = root / "long.wav"
        rate, frames = 48000, 48000 * 600
        values = np.full((65536, 2), 0.25, dtype=np.float32)
        with sf.SoundFile(
            path, "w", samplerate=rate, channels=2, subtype="FLOAT"
        ) as stream:
            for offset in range(0, frames, len(values)):
                stream.write(values[: min(len(values), frames - offset)])
        before = digest(path)
        locator, metadata = prepare_metadata(
            load_media(path).dataset, "file", "", "path", 0, ReferenceSettings(), None
        )
        store = ArrayStore(retained_bytes=1024**2, directory=root)
        try:
            file_report = exercise(
                player,
                PlaybackRequest(locator, metadata, AudioRange(), device=args.device),
                store,
                devices,
                3,
            )
            warm_report = exercise(
                player,
                PlaybackRequest(locator, metadata, AudioRange(), device=args.device),
                store,
                devices,
                0.3,
            )
            assert store.stored_bytes == 0 and store.temporary_path is None
            archive = root / "waves.npz"
            waves = np.full((10, 48000, 2), 0.25, dtype=np.float32)
            np.savez_compressed(archive, waves=waves)
            del waves
            array_before = digest(archive)
            catalog = inspect_arrays(archive)
            mapping = ArrayRecordMapping(
                "waves", layout=ArrayLayout.AUDIO, display_axes=(1,), channel_axis=2
            )
            dataset, _ = prepare_array_records(store, catalog, mapping)
            locator, metadata = prepare_metadata(
                dataset,
                "arrays",
                "waves",
                "waves",
                9,
                ReferenceSettings(),
                None,
                catalog,
                mapping,
                rate,
            )
            array_report = exercise(
                player,
                PlaybackRequest(
                    locator, metadata, AudioRange(), channel=1, device=args.device
                ),
                store,
                devices,
                0.3,
            )
            # A seek is a separate original-source command/lease. Oversized members
            # are released after each, rather than retained beyond the disk budget.
            assert store.extractions == 2 and store.stored_bytes == 0
            temporary_path = store.temporary_path
            assert temporary_path is not None and not tuple(temporary_path.iterdir())
            player.play(
                PlaybackRequest(
                    locator,
                    metadata,
                    AudioRange(),
                    channel=1,
                    device="Datelier missing output acceptance fixture",
                ),
                store,
                volume=0,
            )
            deadline = perf_counter() + 5
            while (
                player.snapshot.phase != PlaybackPhase.FAILED
                and perf_counter() < deadline
            ):
                sleep(0.005)
            failure = player.snapshot
            assert failure.phase == PlaybackPhase.FAILED and failure.cpu_bytes == 0
            assert "Datelier missing output" in failure.message
            assert store.stored_bytes == 0
            player.close()
            assert player.snapshot.phase == PlaybackPhase.CLOSED
            store.close()
            assert not temporary_path.exists()
            assert digest(path) == before and digest(archive) == array_before
            rss = (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - baseline) * 1024
            assert rss < 96 * 1024**2
            report = {
                "file": file_report,
                "file_warm": warm_report,
                "array": array_report,
                "array_extractions": store.extractions,
                "array_extracted_bytes_total": store.extracted_bytes,
                "array_member_temporary_bytes": catalog.member("waves").container_bytes,
                "retained_array_bytes_after_stop": store.stored_bytes,
                "peak_rss_increase_bytes": rss,
                "temporary_cleanup": True,
                "source_preserved": True,
                "volume": 0,
                "native_missing_device_error": failure.message,
                "listening_observation": (
                    "Not recorded; muted physical-device resource instrumentation."
                ),
            }
        finally:
            player.close()
            store.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
