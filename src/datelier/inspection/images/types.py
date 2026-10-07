"""Image recipes and original-pixel worker results, independent of rendering."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from datelier.core.dataset import DatasetRevision
from datelier.inspection.arrays.mapping import ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.references.types import AssetIdentity


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

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height else 0.0


@dataclass(frozen=True)
class ImageDisplay:
    channel: int | None = None
    value_range: tuple[float, float] | None = None

    def validate(self) -> None:
        if self.channel is not None and self.channel < 0:
            raise ValueError("Image channel must be nonnegative")
        if self.value_range is not None:
            lo, hi = self.value_range
            if not np.isfinite(lo) or not np.isfinite(hi) or lo >= hi:
                raise ValueError("Display range needs finite, increasing endpoints")


@dataclass(frozen=True)
class ImageWindow:
    left: int = 0
    top: int = 0
    width: int = 512
    height: int = 512

    def validate(self) -> None:
        if min(self.left, self.top) < 0 or not 1 <= min(self.width, self.height):
            raise ValueError("Image windows require nonnegative origins and sizes")
        if max(self.width, self.height) > 1024:
            raise ValueError("Image windows are at most 1024 pixels per axis")


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

    @property
    def retained_bytes(self) -> int:
        return self.raw.nbytes + self.rgba.nbytes

    def pixel(self, x: int, y: int) -> tuple[object, ...] | None:
        """Read exact oriented coordinates from the prepared original-pixel tile."""
        x, y = x - self.window.left, y - self.window.top
        if not 0 <= x < self.raw.shape[1] or not 0 <= y < self.raw.shape[0]:
            return None
        return tuple(np.atleast_1d(self.raw[y, x]).tolist())
