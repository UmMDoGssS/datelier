"""Saved display/profile choices independent of association input recipes."""

from dataclasses import dataclass
from math import isfinite

from datelier.inspection.annotations.overlay import OverlaySettings


@dataclass(frozen=True)
class AnnotationViewSettings:
    overlay: OverlaySettings = OverlaySettings()
    tab: str = "Sources"
    profile_tab: str = "Classes"
    source_id: str | None = None
    bins: int = 32
    distribution: str = "Width"
    height: float = 0

    def validate(self) -> None:
        self.overlay.validate()
        if not 1 <= self.bins <= 256:
            raise ValueError("Annotation profiles require 1–256 bins")
        if self.tab not in ("Sources", "Associations", "Profiles"):
            raise ValueError("Unknown annotation view")
        if self.profile_tab not in ("Classes", "Sizes", "Quality", "Boxes"):
            raise ValueError("Unknown annotation profile view")
        if self.distribution not in ("Width", "Height", "Area", "Aspect ratio"):
            raise ValueError("Unknown annotation size distribution")
        if not isfinite(self.height) or self.height != 0 and self.height < 170:
            raise ValueError(
                "Annotation plot height requires zero/auto or at least 170 px"
            )
