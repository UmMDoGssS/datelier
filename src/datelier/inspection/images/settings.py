"""Saved image controls; prepared pixels and textures are never serialized."""

from dataclasses import dataclass
from math import isfinite

from datelier.inspection.images.profile_types import ImageProfileSettings
from datelier.inspection.images.types import ImageDisplay
from datelier.inspection.images.viewport import ImageViewport


@dataclass(frozen=True)
class ImageProfileViewSettings:
    tab: str = "Statistics"
    dimension: str = "Width"
    group_mode: str | None = None
    group_dtype: str | None = None
    height: float = 0

    def validate(self) -> None:
        if self.tab not in ("Statistics", "Dimensions", "Colors", "Record outcomes"):
            raise ValueError("Unknown image profile view")
        if self.dimension not in ("Width", "Height", "Aspect ratio"):
            raise ValueError("Unknown image dimension chart")
        if not isfinite(self.height) or self.height != 0 and self.height < 170:
            raise ValueError("Image plot height requires zero/auto or at least 170 px")


@dataclass(frozen=True)
class ImageSettings:
    display: ImageDisplay = ImageDisplay()
    viewport: ImageViewport = ImageViewport()
    cpu_bytes: int = 16 * 1024 * 1024
    gpu_bytes: int = 8 * 1024 * 1024
    disk_bytes: int = 256 * 1024 * 1024
    profile: ImageProfileSettings = ImageProfileSettings()
    profile_view: ImageProfileViewSettings = ImageProfileViewSettings()
    profile_payload: bool = False

    def validate(self) -> None:
        self.display.validate()
        self.viewport.validate()
        self.profile.validate()
        self.profile_view.validate()
        if min(self.cpu_bytes, self.gpu_bytes) < 1024 * 1024 or self.disk_bytes < 0:
            raise ValueError(
                "Image caches require 1 MiB CPU/GPU and nonnegative disk bytes"
            )
