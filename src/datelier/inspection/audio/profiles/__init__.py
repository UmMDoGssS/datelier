"""Explicit blockwise original-signal statistics for chosen ranges/channels.

Profiles retain finite/missing counts, extrema, mean, stable RMS, silence, and
clipping statistics with their units and thresholds. Integer PCM and floating
signals keep distinct amplitude semantics. Header-only metadata is available
without scanning signals; large recordings do not require whole-signal copies.
"""

from datelier.inspection.audio.profiles.types import (
    AudioChannelSummary as AudioChannelSummary,
)
from datelier.inspection.audio.profiles.types import AudioProgress as AudioProgress
from datelier.inspection.audio.profiles.types import (
    AudioSignalProfile as AudioSignalProfile,
)
from datelier.inspection.audio.profiles.types import AudioThresholds as AudioThresholds
