"""Image-space navigation math, without textures or source reads."""

from dataclasses import dataclass
from math import ceil, isfinite

from datelier.inspection.images.types import ImageWindow


@dataclass(frozen=True)
class ImageViewport:
    zoom: float = 1.0
    left: float = 0.0
    top: float = 0.0

    def validate(self) -> None:
        if not 1e-6 <= self.zoom <= 32 or not all(
            isfinite(n) and n >= 0 for n in (self.left, self.top)
        ):
            raise ValueError("Image view needs a finite positive zoom and origin")

    def clamp(
        self, width: int, height: int, size: tuple[float, float]
    ) -> ImageViewport:
        return ImageViewport(
            self.zoom,
            min(max(0, width - size[0] / self.zoom), max(0, self.left)),
            min(max(0, height - size[1] / self.zoom), max(0, self.top)),
        )

    def point(self, x: float, y: float) -> tuple[float, float]:
        return self.left + x / self.zoom, self.top + y / self.zoom

    def zoom_at(self, zoom: float, x: float, y: float) -> ImageViewport:
        sx, sy = self.point(x, y)
        zoom = max(1e-6, min(32, zoom))
        return ImageViewport(zoom, max(0, sx - x / zoom), max(0, sy - y / zoom))

    def pan(self, dx: float, dy: float) -> ImageViewport:
        return ImageViewport(
            self.zoom,
            max(0, self.left - dx / self.zoom),
            max(0, self.top - dy / self.zoom),
        )

    def window(self, size: tuple[float, float]) -> ImageWindow:
        return ImageWindow(
            int(self.left),
            int(self.top),
            max(1, ceil(size[0] / self.zoom) + 1),
            max(1, ceil(size[1] / self.zoom) + 1),
        )
