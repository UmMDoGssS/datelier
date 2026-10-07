"""Explicit record scope and original-unit signal scans, independent of playback."""

from dataclasses import dataclass
from enum import StrEnum

from datelier.inspection.audio.profile_types import AudioThresholds
from datelier.inspection.audio.types import validate_sample_rate


class AudioScopeMode(StrEnum):
    COLLECTION = "All current rows"
    RANGE = "Row range"
    SELECTION = "Linked selection"
    RANDOM = "Seeded random sample"


class AudioProfileMode(StrEnum):
    HEADERS = "Headers only"
    SIGNAL = "Exact signal statistics"


@dataclass(frozen=True)
class AudioScope:
    mode: AudioScopeMode = AudioScopeMode.COLLECTION
    start: int = 1
    count: int = 100
    seed: int = 42

    def validate(self) -> None:
        if min(self.start, self.count) < 1 or not 0 <= self.seed < 2**32:
            raise ValueError("Audio scope needs positive range/count and a 32-bit seed")


@dataclass(frozen=True)
class AudioCollectionSettings:
    column: str | None = None
    scope: AudioScope = AudioScope()
    mode: AudioProfileMode = AudioProfileMode.HEADERS
    array_sample_rate: int | None = None
    thresholds: AudioThresholds = AudioThresholds()

    def validate(self) -> None:
        self.scope.validate()
        self.thresholds.validate()
        validate_sample_rate(self.array_sample_rate)
