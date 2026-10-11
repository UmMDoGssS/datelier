"""Saved audio controls; decoded samples/statistics/playback are not serialized."""

from dataclasses import dataclass
from math import isfinite

from datelier.inspection.audio.collections import AudioCollectionSettings
from datelier.inspection.audio.playback.settings import PlaybackSettings
from datelier.inspection.audio.profiles import AudioThresholds
from datelier.inspection.audio.signal import SignalViewSettings
from datelier.inspection.audio.types import AudioRange, validate_sample_rate


@dataclass(frozen=True)
class AudioSettings:
    array_sample_rate: int | None = None
    range: AudioRange = AudioRange(0, 65536)
    thresholds: AudioThresholds = AudioThresholds()
    channel: int = 0
    cpu_bytes: int = 16 * 1024 * 1024
    view: SignalViewSettings = SignalViewSettings()
    gpu_bytes: int = 8 * 1024 * 1024
    plot_height: float = 240
    playback: PlaybackSettings = PlaybackSettings()
    collection: AudioCollectionSettings = AudioCollectionSettings()
    profile_tab: str = "Records"

    def validate(self) -> None:
        self.view.validate()
        self.playback.validate()
        self.collection.validate()
        if self.profile_tab not in ("Records", "Channels"):
            raise ValueError("Unknown audio collection profile view")
        if self.gpu_bytes < 1024 * 1024:
            raise ValueError("Audio textures require at least 1 MiB GPU retention")
        if (
            not isfinite(self.plot_height)
            or self.plot_height != 0
            and self.plot_height < 170
        ):
            raise ValueError("Audio plot height requires auto/zero or at least 170 px")
        validate_sample_rate(self.array_sample_rate)
        self.thresholds.validate()
        self.range.bounds(max(self.range.start, self.range.stop or 0))
        if self.channel < 0 or self.cpu_bytes < 1024 * 1024:
            raise ValueError(
                "Audio controls need a nonnegative channel and 1 MiB CPU budget"
            )
