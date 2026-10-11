"""One decoder/array lease and device lifetime; no source IO in output callbacks."""

from concurrent.futures import CancelledError
from dataclasses import dataclass, field
from threading import Event

import numpy as np
from numpy.typing import NDArray

from datelier.inspection.audio.playback.buffer import PlaybackRing
from datelier.inspection.audio.playback.conversion import output_samples
from datelier.inspection.audio.playback.device import DeviceFactory
from datelier.inspection.audio.playback.types import (
    BLOCK_FRAMES,
    PlaybackRequest,
    RenderAction,
)
from datelier.inspection.audio.reading import audio_blocks, check_stopped
from datelier.inspection.audio.types import AudioRange
from datelier.io.arrays import ArrayStore


@dataclass
class PlaybackRun:
    request: PlaybackRequest
    arrays: ArrayStore
    serial: int
    volume: float
    paused: bool = False
    stop: Event = field(default_factory=Event)
    ring: PlaybackRing | None = None
    ready: bool = False
    completed: bool = False
    nonfinite: int = 0
    device_underruns: int = 0
    device_name: str = ""
    latency: float = 0
    conversion: str = ""
    callback_error: str = ""


class PlaybackReleaseError(RuntimeError):
    """Device closure was attempted but could not be confirmed."""


def execute_playback(run: PlaybackRun, factory: DeviceFactory) -> None:
    request = run.request
    start, stop = request.first_frame, request.range.bounds(request.metadata.frames)[1]
    if start == stop:
        run.completed = True
        return
    ring = run.ring = PlaybackRing.for_request(request)

    def render(output: NDArray[np.float32], status: bool) -> RenderAction:
        try:
            run.device_underruns += int(status)
            return ring.render(
                output, run.volume, paused=run.paused, stopped=run.stop.is_set()
            )
        except Exception as error:
            output.fill(0)
            run.callback_error = str(error)
            run.stop.set()
            return RenderAction.ABORT

    check_stopped(run.stop.is_set)
    device = factory(request, render)
    run.device_name, run.latency = device.name, device.latency
    try:
        check_stopped(run.stop.is_set)
        with audio_blocks(
            request.locator,
            request.metadata,
            run.arrays,
            AudioRange(start, stop),
            channel=request.channel,
            block_frames=BLOCK_FRAMES,
            block_bytes=request.cpu_bytes,
            stopped=run.stop.is_set,
        ) as blocks:
            eof = False

            def fill() -> None:
                nonlocal eof
                try:
                    block = next(blocks)
                except StopIteration:
                    ring.finish()
                    eof = True
                    return
                samples = output_samples(block.samples)
                run.nonfinite += samples.nonfinite
                run.conversion = samples.description
                if not ring.append(block.start, samples.values):
                    raise RuntimeError("Playback input exceeded reserved ring space")

            while not eof and ring.free >= BLOCK_FRAMES:
                check_stopped(run.stop.is_set)
                fill()
            check_stopped(run.stop.is_set)
            device.start()
            run.ready = True
            while not run.stop.is_set():
                if not device.active:
                    if not eof or ring.count:
                        raise RuntimeError(
                            "Output device stopped before the selected range finished"
                        )
                    run.completed = True
                    break
                if not eof and ring.free >= BLOCK_FRAMES:
                    fill()
                else:
                    run.stop.wait(0.005)
            if run.callback_error:
                raise RuntimeError("Output callback failed: " + run.callback_error)
    finally:
        run.stop.set()
        try:
            try:
                if not run.completed:
                    device.abort()
            finally:
                device.close()
        except Exception as error:
            raise PlaybackReleaseError(
                f"Output device closure failed: {error}"
            ) from error
    if not run.completed:
        raise CancelledError("Playback stopped after device closure")
