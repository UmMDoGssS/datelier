"""Serializable source scopes and view-only image comparison choices."""

import math
from dataclasses import dataclass

from datelier.inspection.images.profiles import ImageProfileSettings


@dataclass(frozen=True)
class ImageComparisonSource:
    file_id: str
    profile: ImageProfileSettings = ImageProfileSettings()

    def validate(self) -> None:
        if not self.file_id or not self.profile.column:
            raise ValueError(
                "Map an image field or confirmed image view from an open file"
            )
        self.profile.validate()


@dataclass(frozen=True)
class ImageComparisonSettings:
    sources: tuple[ImageComparisonSource, ...] = ()
    bins: int = 32

    def validate(self) -> None:
        if not 1 <= self.bins <= 256:
            raise ValueError("Image comparisons require 1–256 common bins")
        if len(self.sources) > 32 or len({s.file_id for s in self.sources}) != len(
            self.sources
        ):
            raise ValueError("Choose one image field per file/view; at most 32 sources")
        for source in self.sources:
            source.validate()


@dataclass(frozen=True)
class ImageComparisonViewSettings:
    tab: str = "Dimensions"
    dimension: str = "Width"
    mode: str | None = None
    dtype: str | None = None
    channel: str = "R"
    proportions: bool = True
    source: int = 0
    bin_index: int = 0
    height: float = 240

    def validate(self) -> None:
        if self.tab not in ("Dimensions", "Colors", "Statistics", "Records"):
            raise ValueError("Unknown image comparison view")
        if self.dimension not in ("Width", "Height", "Aspect ratio"):
            raise ValueError("Unknown image comparison dimension")
        if (
            min(self.source, self.bin_index) < 0
            or not math.isfinite(self.height)
            or self.height != 0
            and self.height < 80
        ):
            raise ValueError("Choose valid image comparison controls")
