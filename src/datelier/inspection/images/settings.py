"""Saved image controls; prepared pixels and textures are never serialized."""

from dataclasses import dataclass

from datelier.inspection.images.types import ImageDisplay
from datelier.inspection.images.viewport import ImageViewport


@dataclass(frozen=True)
class ImageSettings:
    display: ImageDisplay = ImageDisplay()
    viewport: ImageViewport = ImageViewport()
    cpu_bytes: int = 16 * 1024 * 1024
    gpu_bytes: int = 8 * 1024 * 1024
    disk_bytes: int = 256 * 1024 * 1024

    def validate(self) -> None:
        self.display.validate()
        self.viewport.validate()
        if min(self.cpu_bytes, self.gpu_bytes) < 1024 * 1024 or self.disk_bytes < 0:
            raise ValueError(
                "Image caches require 1 MiB CPU/GPU and nonnegative disk bytes"
            )
