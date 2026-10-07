"""Saved audio controls; decoded samples/statistics/playback are not serialized."""

from dataclasses import dataclass

from datelier.inspection.audio.profile_types import AudioThresholds
from datelier.inspection.audio.types import AudioRange, validate_sample_rate


@dataclass(frozen=True)
class AudioSettings:
    array_sample_rate: int | None = None
    range: AudioRange = AudioRange(0, 65536)
    thresholds: AudioThresholds = AudioThresholds()
    channel: int = 0
    cpu_bytes: int = 16 * 1024 * 1024

    def validate(self) -> None:
        validate_sample_rate(self.array_sample_rate)
        self.thresholds.validate()
        self.range.bounds(max(self.range.start, self.range.stop or 0))
        if self.channel < 0 or self.cpu_bytes < 1024 * 1024:
            raise ValueError(
                "Audio controls need a nonnegative channel and 1 MiB CPU budget"
            )
