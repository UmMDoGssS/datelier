"""Original-signal playback requests constructed independently of widgets."""

from datelier.inspection.audio.playback.types import PlaybackRequest
from datelier.inspection.audio.settings import AudioSettings
from datelier.inspection.audio.types import AudioLocator, AudioMetadata, AudioRange


def playback_request(
    prepared: tuple[AudioLocator, AudioMetadata], settings: AudioSettings
) -> PlaybackRequest:
    locator, metadata = prepared
    start = min(settings.range.start, metadata.frames)
    stop = min(
        settings.range.stop if settings.range.stop is not None else metadata.frames,
        metadata.frames,
    )
    selected = (
        AudioRange(start, max(start, stop))
        if settings.playback.selected_range
        else AudioRange(0, metadata.frames)
    )
    return PlaybackRequest(
        locator,
        metadata,
        selected,
        channel=min(settings.channel, metadata.channels - 1)
        if settings.playback.selected_channel
        else None,
        device=settings.playback.device,
        cpu_bytes=settings.cpu_bytes,
    )
