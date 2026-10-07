"""Worker-only image reference resolution and header-first array/file metadata."""

import warnings

import numpy as np
from PIL import Image, TiffImagePlugin

from datelier.core.dataset import Dataset
from datelier.inspection.arrays.mapping import ArrayLayout, ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.images.png import exif_chunk
from datelier.inspection.images.types import ImageLocator, ImageMetadata, ImageOrigin
from datelier.inspection.references.index import ReferenceIndex, resolve
from datelier.inspection.references.types import AssetIdentity, ReferenceSettings


class ImageReferenceError(ValueError):
    """An unresolved reference; its diagnostic retains missing/ambiguous evidence."""


def check_asset(asset: AssetIdentity) -> None:
    stat = asset.path.stat()
    if (stat.st_size, stat.st_mtime_ns) != (asset.size, asset.modified_ns):
        raise ValueError("Image asset changed; reload the record")


def image_mode(mode: str) -> tuple[str, tuple[str, ...], np.dtype[np.generic]]:
    if mode in ("P", "PA"):
        return "RGBA", ("R", "G", "B", "A"), np.dtype("uint8")
    modes = {
        "1": (("L",), "bool"),
        "L": (("L",), "uint8"),
        "LA": (("L", "A"), "uint8"),
        "RGB": (("R", "G", "B"), "uint8"),
        "RGBA": (("R", "G", "B", "A"), "uint8"),
        "CMYK": (("C", "M", "Y", "K"), "uint8"),
        "I": (("Value",), "int32"),
        "F": (("Value",), "float32"),
        "I;16": (("Value",), "uint16"),
        "I;16L": (("Value",), "<u2"),
        "I;16B": (("Value",), ">u2"),
    }
    if mode not in modes:
        raise ValueError(f"Image mode {mode} is unsupported; convert a separate copy")
    channels, dtype = modes[mode]
    return mode, channels, np.dtype(dtype)


def locate_image(
    dataset: Dataset,
    file_id: str,
    view_name: str,
    column: str,
    position: int,
    references: ReferenceSettings,
    index: ReferenceIndex | None,
    catalog: ArrayCatalog | None = None,
    mapping: ArrayRecordMapping | None = None,
) -> ImageLocator:
    if not 0 <= position < dataset.table.height:
        raise ValueError("Image table row is outside the current view")
    row_id = int(dataset.row_ids[position])
    origin = ImageOrigin(file_id, view_name, dataset.revision, row_id, column)
    if catalog is not None and mapping is not None:
        if mapping.layout not in (ArrayLayout.IMAGE, ArrayLayout.HEATMAP):
            raise ValueError("Confirm an image or numeric heatmap record mapping")
        mapping.record_count(catalog)
        return ImageLocator(
            origin, catalog=catalog, mapping=mapping, source_index=row_id
        )
    value = dataset.table.get_column(column)[position]
    if value is None:
        raise ValueError("Image reference is null")
    if not isinstance(value, str) or not value:
        raise ValueError("Image reference requires a nonempty path or mapped value")
    resolved = resolve(dataset.source.path, column, value, references, index)
    if resolved.asset is None:
        raise ImageReferenceError(
            resolved.message or "Choose an explicit image mapping"
        )
    return ImageLocator(origin, asset=resolved.asset)


def image_metadata(locator: ImageLocator) -> ImageMetadata:
    asset = locator.asset
    if asset is not None:
        check_asset(asset)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(asset.path) as image:
                if image.format == "PNG" and "exif" not in image.info:
                    exif = exif_chunk(asset)
                    if exif is not None:
                        image.info["exif"] = exif
                # The PNG override calls load() when EXIF is absent. The base
                # method reads header metadata without decoding source pixels.
                orientation = int(Image.Image.getexif(image).get(274, 1))
                orientation = orientation if 1 <= orientation <= 8 else 1
                mode, channels, dtype = image_mode(image.mode)
                width, height = image.size
                if isinstance(image, TiffImagePlugin.TiffImageFile):
                    # TIFF's header size is already orientation-adjusted by
                    # Pillow; the original grid remains in the directory tags.
                    width, height = int(image.tag_v2[256]), int(image.tag_v2[257])
                w, h = (height, width) if orientation >= 5 else (width, height)
                result = ImageMetadata(
                    width,
                    height,
                    w,
                    h,
                    channels,
                    dtype,
                    mode,
                    orientation,
                    getattr(image, "n_frames", 1),
                    f"{image.mode}; original decoded pixels; first frame"
                    + (
                        "; palette expanded to RGBA"
                        if image.mode in ("P", "PA")
                        else ""
                    ),
                )
        check_asset(asset)
        return result
    catalog, mapping = locator.catalog, locator.mapping
    if catalog is None or mapping is None:
        raise ValueError("Image source is unavailable")
    from datelier.io.arrays.storage import ArrayStore

    ArrayStore.check_source(catalog)
    member = catalog.member(mapping.member)
    assert member.dtype is not None
    if member.dtype.kind not in "biuf":
        raise ValueError("Image arrays need real numeric or boolean values")
    height, width = (member.shape[axis] for axis in mapping.display_axes)
    count = (
        member.shape[mapping.channel_axis] if mapping.channel_axis is not None else 1
    )
    if min(width, height, count) == 0:
        raise ValueError("Image array has an empty spatial or channel dimension")
    if mapping.layout == ArrayLayout.IMAGE and count not in (1, 2, 3, 4):
        raise ValueError("Image mapping requires 1, 2, 3 or 4 channels; use a heatmap")
    names = {1: ("L",), 2: ("L", "A"), 3: ("R", "G", "B"), 4: ("R", "G", "B", "A")}
    channels = names[count] if mapping.layout == ArrayLayout.IMAGE else ("Value",)
    mode = {1: "L", 2: "LA", 3: "RGB", 4: "RGBA"}.get(count, "Numeric")
    return ImageMetadata(
        width,
        height,
        width,
        height,
        channels,
        member.dtype,
        mode if mapping.layout == ArrayLayout.IMAGE else "Numeric",
        description=f"{mapping.member}; raw {member.dtype}; confirmed {mapping.layout}",
        channel_count=count,
    )


def prepare_metadata(
    dataset: Dataset,
    file_id: str,
    view_name: str,
    column: str,
    position: int,
    references: ReferenceSettings,
    index: ReferenceIndex | None,
    catalog: ArrayCatalog | None = None,
    mapping: ArrayRecordMapping | None = None,
) -> tuple[ImageLocator, ImageMetadata]:
    locator = locate_image(
        dataset,
        file_id,
        view_name,
        column,
        position,
        references,
        index,
        catalog,
        mapping,
    )
    return locator, image_metadata(locator)
