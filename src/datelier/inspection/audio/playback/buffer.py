"""Preallocated ring: worker fills; output callback never reads or waits for input."""

from threading import Lock

import numpy as np
from numpy.typing import NDArray

from datelier.inspection.audio.playback.types import (
    BLOCK_FRAMES,
    PlaybackRequest,
    RenderAction,
)


class PlaybackRing:
    def __init__(
        self,
        capacity: int,
        channels: int,
        start: int,
        *,
        block_frames: int = BLOCK_FRAMES,
    ) -> None:
        if capacity < 1 or channels < 1 or block_frames < 1:
            raise ValueError("Playback buffers require positive sizes")
        self.samples = np.empty((capacity, channels), dtype=np.float64)
        self.scratch = np.empty((block_frames, channels), dtype=np.float64)
        self.lock = Lock()
        self.read = self.write = self.count = 0
        self.position = self.next_input = start
        self.finished = False
        self.underruns = 0

    @classmethod
    def for_request(cls, request: PlaybackRequest) -> PlaybackRing:
        request.validate()
        frames = request.cpu_bytes // (request.channels * 8) - BLOCK_FRAMES
        capacity = min(8 * BLOCK_FRAMES, frames // BLOCK_FRAMES * BLOCK_FRAMES)
        if capacity < BLOCK_FRAMES:
            raise ValueError(
                "Playback budget cannot hold a complete output block; "
                "choose one channel or raise audio memory"
            )
        return cls(capacity, request.channels, request.first_frame)

    @property
    def retained_bytes(self) -> int:
        return self.samples.nbytes + self.scratch.nbytes

    @property
    def free(self) -> int:
        with self.lock:
            return len(self.samples) - self.count

    def append(self, start: int, values: NDArray[np.float64]) -> bool:
        with self.lock:
            if self.finished or start != self.next_input:
                raise ValueError(
                    "Playback samples must follow contiguous original frames"
                )
            if values.ndim != 2 or values.shape[1] != self.samples.shape[1]:
                raise ValueError("Playback sample channels changed")
            if len(values) > len(self.samples) - self.count:
                return False
            first = min(len(values), len(self.samples) - self.write)
            self.samples[self.write : self.write + first] = values[:first]
            self.samples[: len(values) - first] = values[first:]
            self.write = (self.write + len(values)) % len(self.samples)
            self.count += len(values)
            self.next_input += len(values)
            return True

    def finish(self) -> None:
        with self.lock:
            self.finished = True

    def render(
        self, output: NDArray[np.float32], volume: float, *, paused: bool, stopped: bool
    ) -> RenderAction:
        output.fill(0)
        if stopped:
            return RenderAction.ABORT
        if paused:
            return RenderAction.CONTINUE
        # A busy producer must never block the real-time device callback.
        if not self.lock.acquire(blocking=False):
            self.underruns += 1
            return RenderAction.CONTINUE
        try:
            offset = 0
            while self.count and offset < len(output):
                count = min(
                    len(output) - offset,
                    self.count,
                    len(self.samples) - self.read,
                    len(self.scratch),
                )
                scratch = self.scratch[:count]
                np.multiply(
                    self.samples[self.read : self.read + count], volume, out=scratch
                )
                np.clip(scratch, -1, 1, out=scratch)
                output[offset : offset + count] = scratch
                self.read = (self.read + count) % len(self.samples)
                self.count -= count
                self.position += count
                offset += count
            if not self.count and self.finished:
                return RenderAction.FINISH
            if offset < len(output):
                self.underruns += 1
            return RenderAction.CONTINUE
        finally:
            self.lock.release()
