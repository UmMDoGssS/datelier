"""Explicit original-rate playback through one lazy worker-owned output device.

Bounded buffers convert for output with visible volume, clipping, and nonfinite
handling. Play/pause/resume/seek/stop are commands; open/restore never starts sound.
Device/rate errors remain diagnostic. Linux requires the PortAudio runtime
(``libportaudio2`` on Debian/Ubuntu); device availability is host-dependent.
Automated command/lifecycle checks pass, but human listening was deferred by the
user on 2026-10-08 and remains unverified.
"""

from datelier.inspection.audio.playback.settings import (
    PlaybackSettings as PlaybackSettings,
)
from datelier.inspection.audio.playback.types import PlaybackRequest as PlaybackRequest
from datelier.inspection.audio.playback.types import RenderAction as RenderAction
