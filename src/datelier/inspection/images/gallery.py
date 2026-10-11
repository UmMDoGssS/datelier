"""Worker-prepared bounded array images; gallery overviews preserve source pixels."""

from dataclasses import dataclass
from math import ceil

import numpy as np
from numpy.typing import NDArray

from datelier.core.dataset import Dataset
from datelier.inspection.arrays.mapping import ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.images.prepare import prepare_window
from datelier.inspection.images.sources import prepare_metadata
from datelier.inspection.images.storage import ImageStore
from datelier.inspection.images.types import ImageDisplay, ImageOrigin, ImageWindow
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays import ArrayStore


@dataclass(frozen=True)
class GalleryImage:
    origin: ImageOrigin
    rgba: NDArray[np.uint8]
    description: str
    step: int

    @property
    def retained_bytes(self) -> int:
        return self.rgba.nbytes


def prepare_gallery_image(
    dataset: Dataset,
    file_id: str,
    view_name: str,
    column: str,
    position: int,
    catalog: ArrayCatalog,
    mapping: ArrayRecordMapping,
    display: ImageDisplay,
    size: int,
    arrays: ArrayStore,
) -> GalleryImage:
    locator, metadata = prepare_metadata(
        dataset,
        file_id,
        view_name,
        column,
        position,
        ReferenceSettings(),
        None,
        catalog,
        mapping,
    )
    step = max(1, ceil(max(metadata.width, metadata.height) / size))
    # This path reads an array member and never creates a decoded file cache.
    images = ImageStore(retained_bytes=0)
    try:
        prepared = prepare_window(
            locator,
            metadata,
            ImageWindow(width=metadata.width, height=metadata.height, step=step),
            display,
            images,
            arrays,
            1024 * 1024,
        )
        return GalleryImage(
            locator.origin,
            prepared.rgba,
            f"{metadata.width}×{metadata.height} · {metadata.dtype} · {metadata.mode}",
            prepared.window.step,
        )
    finally:
        images.cleanup()
