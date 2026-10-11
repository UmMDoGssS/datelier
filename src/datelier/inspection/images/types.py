"""Image recipes and original-pixel worker results, independent of rendering."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from datelier.core import DatasetRevision
from datelier.inspection.arrays import ArrayCatalog, ArrayRecordMapping
from datelier.inspection.heatmaps import Colormap, validate_range
from datelier.inspection.references import AssetIdentity


@dataclass(frozen=True)
class ImageOrigin:
    file_id: str
    view_name: str
    revision: DatasetRevision
    row_id: int
    column: str


@dataclass(frozen=True)
class ImageLocator:
    origin: ImageOrigin
    asset: AssetIdentity | None = None
    catalog: ArrayCatalog | None = None
    mapping: ArrayRecordMapping | None = None
    source_index: int | None = None


@dataclass(frozen=True)
class ImageMetadata:
    source_width: int
    source_height: int
    width: int
    height: int
    channels: tuple[str, ...]
    dtype: np.dtype[np.generic]
    mode: str
    orientation: int = 1
    frames: int = 1
    description: str = ""
    channel_count: int = 0

    @property
    def count(self) -> int:
        return self.channel_count or len(self.channels)

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height else 0.0


@dataclass(frozen=True)
class ImageDisplay:
    channel: int | None = None
    value_range: tuple[float, float] | None = None
    colormap: Colormap = Colormap.GRAY
    fixed: tuple[int, ...] = ()

    def validate(self) -> None:
        if self.channel is not None and self.channel < 0:
            raise ValueError("Image channel must be nonnegative")
        validate_range(self.value_range)
        if self.colormap not in Colormap:
            raise ValueError("Unknown heatmap colormap")
        if len(self.fixed) > 64 or any(index < 0 for index in self.fixed):
            raise ValueError("Heatmap fixed coordinates must be nonnegative")


@dataclass(frozen=True)
class ImageWindow:
    left: int = 0
    top: int = 0
    width: int = 512
    height: int = 512
    step: int = 1

    def validate(self) -> None:
        if min(self.left, self.top) < 0 or not 1 <= min(self.width, self.height):
            raise ValueError("Image windows require nonnegative origins and sizes")
        if self.step < 1:
            raise ValueError("Image sampling step must be positive")


@dataclass(frozen=True)
class PreparedImage:
    locator: ImageLocator
    metadata: ImageMetadata
    window: ImageWindow
    display: ImageDisplay
    raw: NDArray[np.generic]
    rgba: NDArray[np.uint8]
    nonfinite: int
    limited: bool = False
    finite_range: tuple[int | float, int | float] | None = None
    display_range: tuple[int | float, int | float] | None = None

    @property
    def retained_bytes(self) -> int:
        return self.raw.nbytes + self.rgba.nbytes

    def pixel(self, x: int, y: int) -> tuple[object, ...] | None:
        """Read exact oriented coordinates from the prepared original-pixel tile."""
        x, y = x - self.window.left, y - self.window.top
        if x % self.window.step or y % self.window.step:
            return None
        x, y = x // self.window.step, y // self.window.step
        if not 0 <= x < self.raw.shape[1] or not 0 <= y < self.raw.shape[0]:
            return None
        return tuple(np.atleast_1d(self.raw[y, x]).tolist())
