"""Saved explicit audio mappings and common distribution/view controls."""

from dataclasses import dataclass

from datelier.inspection.audio.collections.settings import AudioCollectionSettings


@dataclass(frozen=True)
class AudioComparisonSource:
    file_id: str
    profile: AudioCollectionSettings = AudioCollectionSettings()

    def validate(self) -> None:
        if not self.file_id or not self.profile.column:
            raise ValueError("Map an audio field or confirmed waveform view")
        self.profile.validate()


@dataclass(frozen=True)
class AudioComparisonSettings:
    sources: tuple[AudioComparisonSource, ...] = ()
    bins: int = 32

    def validate(self) -> None:
        if not 1 <= self.bins <= 256:
            raise ValueError("Audio comparisons require 1–256 common bins")
        if len(self.sources) > 32 or len({s.file_id for s in self.sources}) != len(
            self.sources
        ):
            raise ValueError("Choose one audio field per file/view; at most 32 sources")
        for source in self.sources:
            source.validate()


@dataclass(frozen=True)
class AudioComparisonViewSettings:
    tab: str = "Distributions"
    metric: str = "Duration"
    family: str = "seconds"
    channel: int | None = None
    proportions: bool = True
    source: int = 0
    bin_index: int = 0
    height: int = 240

    def validate(self) -> None:
        if self.tab not in ("Distributions", "Statistics", "Records"):
            raise ValueError("Unknown audio comparison view")
        if (
            not self.metric
            or not self.family
            or self.channel is not None
            and self.channel < 0
        ):
            raise ValueError("Choose an available audio metric and unit family")
        if min(self.source, self.bin_index) < 0 or not 80 <= self.height <= 800:
            raise ValueError("Choose valid audio comparison controls")
