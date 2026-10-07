"""A single lazy playback worker coalesces commands and owns the output device."""

from concurrent.futures import CancelledError
from dataclasses import dataclass, replace
from enum import StrEnum
from math import isfinite
from threading import Condition, Thread

from datelier.inspection.audio.playback.device import DeviceFactory, SoundDeviceOutput
from datelier.inspection.audio.playback.types import PlaybackRequest
from datelier.inspection.audio.playback.worker import (
    PlaybackReleaseError,
    PlaybackRun,
    execute_playback,
)
from datelier.io.arrays.storage import ArrayStore


class PlaybackPhase(StrEnum):
    IDLE = "Stopped"
    STARTING = "Preparing playback"
    PLAYING = "Playing"
    PAUSED = "Paused"
    STOPPING = "Closing playback"
    FINISHED = "Playback finished"
    FAILED = "Playback failed"
    CLOSED = "Playback closed"


@dataclass(frozen=True)
class PlaybackSnapshot:
    phase: PlaybackPhase = PlaybackPhase.IDLE
    request: PlaybackRequest | None = None
    position: int = 0  # Next original sample frame submitted to the device.
    cpu_bytes: int = 0
    nonfinite: int = 0
    underruns: int = 0
    device: str = ""
    latency: float = 0
    conversion: str = ""
    message: str = "Playback requires an explicit Play command."


def validate_volume(volume: float) -> None:
    if not isfinite(volume) or not 0 <= volume <= 1:
        raise ValueError("Playback volume must be finite, from 0 to 1")


class AudioPlayback:
    def __init__(self, factory: DeviceFactory = SoundDeviceOutput) -> None:
        self._factory = factory
        self._condition = Condition()
        self._thread: Thread | None = None
        self._pending: PlaybackRun | None = None
        self._run: PlaybackRun | None = None
        self._serial = 0
        self._closed = False
        self._state = PlaybackSnapshot()

    @property
    def snapshot(self) -> PlaybackSnapshot:
        with self._condition:
            state, run = self._state, self._run
            if run is None or run.serial != self._serial:
                return state
            ring = run.ring
            phase = state.phase
            if run.ready and phase != PlaybackPhase.STOPPING:
                phase = PlaybackPhase.PAUSED if run.paused else PlaybackPhase.PLAYING
            return replace(
                state,
                phase=phase,
                position=ring.position if ring is not None else state.position,
                cpu_bytes=ring.retained_bytes if ring is not None else 0,
                nonfinite=run.nonfinite,
                underruns=run.device_underruns
                + (ring.underruns if ring is not None else 0),
                device=run.device_name,
                latency=run.latency,
                conversion=run.conversion,
            )

    def play(
        self,
        request: PlaybackRequest,
        arrays: ArrayStore,
        *,
        volume: float = 0.5,
        paused: bool = False,
    ) -> None:
        request.validate()
        validate_volume(volume)
        with self._condition:
            if self._closed:
                raise RuntimeError("Playback is closed")
            self._serial += 1
            self._pending = PlaybackRun(request, arrays, self._serial, volume, paused)
            if self._run is not None:
                self._run.stop.set()
            self._state = PlaybackSnapshot(
                PlaybackPhase.STARTING,
                request,
                request.first_frame,
                message="Preparing original-rate playback…",
            )
            if self._thread is None:
                self._thread = Thread(target=self._work, name="audio-playback")
                self._thread.start()
            self._condition.notify()

    def pause(self, paused: bool = True) -> None:
        with self._condition:
            if self._pending is not None:
                self._pending.paused = paused
            if self._run is not None:
                self._run.paused = paused

    def set_volume(self, volume: float) -> None:
        validate_volume(volume)
        with self._condition:
            if self._pending is not None:
                self._pending.volume = volume
            if self._run is not None:
                self._run.volume = volume

    def seek(self, frame: int) -> None:
        with self._condition:
            run = self._pending or self._run
            if run is None or self._state.phase == PlaybackPhase.STOPPING:
                raise ValueError("Start or pause a record before seeking")
            request, arrays, volume, paused = (
                replace(run.request, start_frame=frame),
                run.arrays,
                run.volume,
                run.paused,
            )
        self.play(request, arrays, volume=volume, paused=paused)

    def stop(self, file_id: str | None = None) -> None:
        with self._condition:
            request = self._state.request
            if file_id is not None and (
                request is None or request.locator.origin.file_id != file_id
            ):
                return
            self._state = self.snapshot
            self._serial += 1
            self._pending = None
            if self._run is not None:
                self._run.stop.set()
                self._state = replace(
                    self._state,
                    phase=PlaybackPhase.STOPPING,
                    message="Stopping; source/device closure is in progress.",
                )
            elif self._state.phase != PlaybackPhase.FAILED:
                self._state = replace(
                    self._state,
                    phase=PlaybackPhase.IDLE,
                    cpu_bytes=0,
                    message="Playback stopped; device released.",
                )
            self._condition.notify()

    def close(self, *, wait: bool = True) -> None:
        with self._condition:
            self._closed = True
        self.stop()
        with self._condition:
            if self._thread is None:
                self._state = replace(self._state, phase=PlaybackPhase.CLOSED)
            self._condition.notify()
            thread = self._thread
        if wait and thread is not None:
            thread.join()

    def _work(self) -> None:
        while True:
            with self._condition:
                self._condition.wait_for(
                    lambda: self._pending is not None or self._closed
                )
                if self._closed:
                    self._state = replace(
                        self._state, phase=PlaybackPhase.CLOSED, cpu_bytes=0
                    )
                    return
                run, self._pending = self._pending, None
                assert run is not None
                self._run = run
            error = ""
            release_failed = False
            try:
                execute_playback(run, self._factory)
            except CancelledError:
                pass
            except Exception as failure:
                error = str(failure)
                release_failed = isinstance(failure, PlaybackReleaseError)
            finally:
                with self._condition:
                    if release_failed:
                        # A pending source cannot open a second device after an
                        # unconfirmed closure. Surface the failure across owners.
                        self._pending = None
                    if run.serial == self._serial or release_failed:
                        ring = run.ring
                        self._state = PlaybackSnapshot(
                            PlaybackPhase.FAILED
                            if error
                            else PlaybackPhase.FINISHED
                            if run.completed
                            else PlaybackPhase.IDLE,
                            run.request,
                            ring.position
                            if ring is not None
                            else run.request.first_frame,
                            nonfinite=run.nonfinite,
                            underruns=run.device_underruns
                            + (ring.underruns if ring is not None else 0),
                            device=run.device_name,
                            latency=run.latency,
                            conversion=run.conversion,
                            message="Playback failed: " + error
                            if error
                            else "Playback finished; device released."
                            if run.completed
                            else "Playback stopped; device released.",
                        )
                    elif self._pending is None:
                        self._state = replace(
                            self._state,
                            phase=PlaybackPhase.IDLE,
                            cpu_bytes=0,
                            message="Playback stopped; source/device released.",
                        )
                    self._run = None
            # Idle workers must not retain leases or decoded/ring buffers.
            del run
