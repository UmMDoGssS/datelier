"""Saved listening preferences, never an active stream or autoplay instruction."""

from dataclasses import dataclass

from datelier.inspection.audio.playback.controller import validate_volume


@dataclass(frozen=True)
class PlaybackSettings:
    volume: float = 0.5
    selected_range: bool = True
    selected_channel: bool = False
    device: str | None = None
    seek_frame: int | None = None

    def validate(self) -> None:
        validate_volume(self.volume)
        if self.seek_frame is not None and self.seek_frame < 0:
            raise ValueError("Saved playback seek frame must be nonnegative")
        if self.device is not None and not self.device.strip():
            raise ValueError(
                "Saved output device needs a name or the default/empty option"
            )
