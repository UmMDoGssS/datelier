"""Explicit original-source playback recipes and bounded output-buffer contracts."""

from dataclasses import dataclass
from enum import StrEnum

from datelier.inspection.audio.types import AudioLocator, AudioMetadata, AudioRange

BLOCK_FRAMES = 512


class RenderAction(StrEnum):
    CONTINUE = "continue"
    FINISH = "finish"
    ABORT = "abort"


@dataclass(frozen=True)
class PlaybackRequest:
    locator: AudioLocator
    metadata: AudioMetadata
    range: AudioRange
    channel: int | None = None  # None preserves all original channels.
    start_frame: int | None = None
    device: str | None = None
    cpu_bytes: int = 1024 * 1024

    @property
    def channels(self) -> int:
        return self.metadata.channels if self.channel is None else 1

    @property
    def first_frame(self) -> int:
        return self.range.start if self.start_frame is None else self.start_frame

    def validate(self) -> None:
        self.metadata.require_rate()
        start, stop = self.range.bounds(self.metadata.frames)
        if start == stop:
            raise ValueError("Choose a nonempty playback range")
        if not start <= self.first_frame <= stop:
            raise ValueError("Seek within the chosen playback range")
        if self.channel is not None and not 0 <= self.channel < self.metadata.channels:
            raise ValueError("Playback channel is outside the original signal")
        if self.channels < 1 or self.cpu_bytes < 1:
            raise ValueError("Playback channels and buffer budget must be positive")
