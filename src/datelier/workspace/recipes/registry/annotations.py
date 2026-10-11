"""Trusted annotations recipe records; never selected by file-supplied imports."""

from datelier.inspection.annotations.overlay import OverlayClass, OverlaySettings
from datelier.inspection.annotations.settings import (
    AnnotationSettings,
    AnnotationSource,
    ImageAssociationMapping,
)
from datelier.inspection.annotations.types import AnnotationClass
from datelier.inspection.annotations.view_settings import AnnotationViewSettings

RECORDS = (
    AnnotationViewSettings,
    OverlayClass,
    OverlaySettings,
    AnnotationSettings,
    AnnotationSource,
    ImageAssociationMapping,
    AnnotationClass,
)
