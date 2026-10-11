"""Trusted audio recipe records; never selected by file-supplied imports."""

from datelier.inspection.audio.collections.settings import (
    AudioCollectionSettings,
    AudioScope,
)
from datelier.inspection.audio.comparisons.settings import (
    AudioComparisonSettings,
    AudioComparisonSource,
    AudioComparisonViewSettings,
)
from datelier.inspection.audio.playback.settings import PlaybackSettings
from datelier.inspection.audio.profile_types import AudioThresholds
from datelier.inspection.audio.settings import AudioSettings
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.audio.view_types import SignalViewSettings

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
