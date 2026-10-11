"""Explicit signal thresholds, channel summaries and scan progress."""

from dataclasses import dataclass
from math import isfinite
from threading import Lock

from datelier.inspection.audio.types import AudioLocator, AudioMetadata, AudioRange


@dataclass(frozen=True)
class AudioThresholds:
    clipping: float | None = None  # None uses original PCM/dtype rails, or ±1.
    silence: float = 0.0001  # Absolute amplitude in the original signal's units.

    def validate(self) -> None:
        if self.clipping is not None and (
            not isfinite(self.clipping) or self.clipping <= 0
        ):
            raise ValueError("Clipping amplitude must be finite and positive")
        if not isfinite(self.silence) or self.silence < 0:
            raise ValueError("Silence amplitude must be finite and nonnegative")


@dataclass(frozen=True)
class AudioChannelSummary:
    channel: int
    samples: int
    finite: int
    nonfinite: int
    minimum: str | None
    maximum: str | None
    peak: str | None
    mean: float | None
    rms: float | None
    clipped: int
    silent: int
    diagnostic: str = ""


@dataclass(frozen=True)
class AudioSignalProfile:
    locator: AudioLocator
    metadata: AudioMetadata
    range: AudioRange
    thresholds: AudioThresholds
    clipping_bounds: tuple[int | float, int | float]
    channels: tuple[AudioChannelSummary, ...]
    silent_frames: int  # All channels finite and within the silence threshold.
    longest_silence_frames: int
    nonfinite_frames: int

    @property
    def frames(self) -> int:
        assert self.range.stop is not None
        return self.range.stop - self.range.start

    @property
    def duration(self) -> float:
        return self.frames / self.metadata.require_rate()

    @property
    def silence_duration(self) -> float:
        return self.silent_frames / self.metadata.require_rate()


class AudioProgress:
    def __init__(self) -> None:
        self._lock = Lock()
        self._value = (0, 0)

    @property
    def value(self) -> tuple[int, int]:
        with self._lock:
            return self._value

    def update(self, done: int, total: int) -> None:
        with self._lock:
            self._value = done, total
