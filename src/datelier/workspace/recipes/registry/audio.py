"""Trusted audio recipe records; never selected by file-supplied imports."""

from datelier.inspection.audio.collections import (
    AudioCollectionSettings,
    AudioScope,
)
from datelier.inspection.audio.comparisons import (
    AudioComparisonSettings,
    AudioComparisonSource,
    AudioComparisonViewSettings,
)
from datelier.inspection.audio.playback.settings import PlaybackSettings
from datelier.inspection.audio.profiles import AudioThresholds
from datelier.inspection.audio.settings import AudioSettings
from datelier.inspection.audio.signal import SignalViewSettings
from datelier.inspection.audio.types import AudioRange

RECORDS = (
    AudioCollectionSettings,
    AudioScope,
    AudioComparisonSettings,
    AudioComparisonSource,
    AudioComparisonViewSettings,
    PlaybackSettings,
    SignalViewSettings,
    AudioRange,
    AudioThresholds,
    AudioSettings,
)
