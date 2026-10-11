"""Explicit quiet output-device lifecycle; cursor evidence is submitted samples."""

import argparse
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter, sleep

import numpy as np
import soundfile as sf

from datelier.inspection.audio.decoding import prepare_metadata
from datelier.inspection.audio.playback.controller import (
    AudioPlayback,
    PlaybackPhase,
    PlaybackSnapshot,
)
from datelier.inspection.audio.playback.types import PlaybackRequest
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays import ArrayStore
from datelier.io.media import load_media


def wait(
    player: AudioPlayback, ready: Callable[[PlaybackSnapshot], bool]
) -> PlaybackSnapshot:
    deadline = perf_counter() + 5
    while perf_counter() < deadline:
        state = player.snapshot
        assert state.phase != PlaybackPhase.FAILED, state.message
        if ready(state):
            return state
        sleep(0.005)
    raise AssertionError(player.snapshot)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="datelier-output-lifecycle-") as temporary:
        source = Path(temporary) / "tones.wav"
        rate = 48000
        positions = np.arange(rate * 3) / rate
        frequencies = np.where(positions < 1, 440, np.where(positions < 2, 660, 880))
        wave = 0.25 * np.sin(2 * np.pi * frequencies * positions)
        sf.write(source, np.stack((wave, -wave), axis=1), rate, subtype="FLOAT")
        original = hashlib.sha256(source.read_bytes()).hexdigest()
        locator, metadata = prepare_metadata(
            load_media(source).dataset,
            "native",
            "audio",
            "path",
            0,
            ReferenceSettings(),
            None,
        )
        store, player = ArrayStore(), AudioPlayback()
        try:
            started = perf_counter()
            player.play(
                PlaybackRequest(locator, metadata, AudioRange(), device=args.device),
                store,
                volume=0.25,
            )
            state = wait(
                player,
                lambda state: (
                    state.phase == PlaybackPhase.PLAYING and state.position > 0
                ),
            )
            startup = perf_counter() - started
            device, latency, retained = state.device, state.latency, state.cpu_bytes
            assert startup < 2 and retained <= 1024**2
            player.pause()
            started = perf_counter()
            sleep(0.05)  # Two output blocks plus the reported low device latency.
            paused = player.snapshot.position
            sleep(0.05)
            assert (
                player.snapshot.phase == PlaybackPhase.PAUSED
                and player.snapshot.position == paused
            )
            pause = perf_counter() - started
            assert pause < 0.3
            started = perf_counter()
            player.seek(rate * 2)
            state = wait(
                player,
                lambda state: (
                    state.phase == PlaybackPhase.PAUSED
                    and state.request is not None
                    and state.request.first_frame == rate * 2
                ),
            )
            seek = perf_counter() - started
            assert seek < 0.3 and state.position == rate * 2
            player.set_volume(0.125)
            player.pause(False)
            state = wait(
                player,
                lambda state: (
                    state.phase == PlaybackPhase.PLAYING and state.position > rate * 2
                ),
            )
            assert (
                state.request is not None and state.request.locator.origin.row_id == 0
            )
            assert state.request.metadata.sample_rate == rate
            started = perf_counter()
            player.stop()
            state = wait(player, lambda state: state.phase == PlaybackPhase.IDLE)
            stopped = perf_counter() - started
            assert stopped < 0.3 and state.cpu_bytes == 0
            player.close()
            assert player.snapshot.phase == PlaybackPhase.CLOSED
            assert hashlib.sha256(source.read_bytes()).hexdigest() == original
            report = {
                "device": device,
                "original_sample_rate": rate,
                "channels": 2,
                "startup_seconds": startup,
                "pause_stable_seconds": pause,
                "paused_seek_seconds": seek,
                "stop_closed_seconds": stopped,
                "device_latency_seconds": latency,
                "retained_output_bytes": retained,
                "retained_after_stop": state.cpu_bytes,
                "output_underruns": state.underruns,
                "paused_cursor_stable": True,
                "seek_paused_without_output": True,
                "seek_original_frame": rate * 2,
                "volume_changed": True,
                "source_preserved": True,
                "device_closed": True,
                "cursor_basis": "original sample frames submitted to the output device",
                "listening_observation": (
                    "Not recorded; this is device/cursor instrumentation."
                ),
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report))
        finally:
            player.close()
            store.close()


if __name__ == "__main__":
    main()
