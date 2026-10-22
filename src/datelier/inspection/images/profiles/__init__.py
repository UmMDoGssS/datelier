"""Explicit exact/sampled image collection statistics with source outcomes.

Scopes support current rows, ranges, selections, seeded records, and separately
seeded pixels. Original pixels are exact by default; statistics, dimensions,
colors, failures, and sampling provenance accompany every result. Preparation
uses bounded scans/stores rather than retaining decoded collections.
"""

from datelier.inspection.images.profiles.types import ChannelKey as ChannelKey
from datelier.inspection.images.profiles.types import ChannelSummary as ChannelSummary
from datelier.inspection.images.profiles.types import ImageBounds as ImageBounds
from datelier.inspection.images.profiles.types import ImageHistogram as ImageHistogram
from datelier.inspection.images.profiles.types import ImageProfile as ImageProfile
from datelier.inspection.images.profiles.types import (
    ImageProfileSettings as ImageProfileSettings,
)
from datelier.inspection.images.profiles.types import ImageProgress as ImageProgress
from datelier.inspection.images.profiles.types import ImageScope as ImageScope
from datelier.inspection.images.profiles.types import ImageScopeMode as ImageScopeMode
from datelier.inspection.images.profiles.types import PixelScope as PixelScope
