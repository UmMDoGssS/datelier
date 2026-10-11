"""Trusted images recipe records; never selected by file-supplied imports."""

from datelier.inspection.images.comparisons.settings import (
    ImageComparisonSettings,
    ImageComparisonSource,
    ImageComparisonViewSettings,
)
from datelier.inspection.images.profiles import ImageProfileSettings, ImageScope
from datelier.inspection.images.settings import ImageProfileViewSettings, ImageSettings
from datelier.inspection.images.types import ImageDisplay
from datelier.inspection.images.viewport import ImageViewport

RECORDS = (
    ImageComparisonSettings,
    ImageComparisonSource,
    ImageComparisonViewSettings,
    ImageProfileSettings,
    ImageScope,
    ImageProfileViewSettings,
    ImageSettings,
    ImageDisplay,
    ImageViewport,
)
