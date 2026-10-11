"""Small visible previews decoded entirely outside frame callbacks."""

import warnings

import numpy as np
from PIL import Image, ImageOps

from datelier.core.column_roles import IMAGE_EXTENSIONS, TEXT_EXTENSIONS
from datelier.inspection.references.types import AssetIdentity, AssetPreview


def decode(asset: AssetIdentity, size: int) -> AssetPreview:
    try:
        suffix = asset.path.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(asset.path) as image:
                    description = (
                        f"{image.width}×{image.height} {image.mode}; first frame"
                    )
                    image.thumbnail((size, size))
                    oriented = ImageOps.exif_transpose(image)
                    rgba = np.asarray(oriented.convert("RGBA")).copy()
                    rgba.flags.writeable = False
            result = AssetPreview(
                asset,
                rgba=rgba,
                description=description + f"; {rgba.shape[1]}×{rgba.shape[0]} preview",
            )
        elif suffix in TEXT_EXTENSIONS:
            with asset.path.open("rb") as stream:
                data = stream.read(4097)
            result = AssetPreview(
                asset,
                text=data[:4096].decode("utf8", errors="replace"),
                description="UTF-8 excerpt, first 4096 bytes"
                + (" (truncated)" if len(data) > 4096 else ""),
            )
        else:
            result = AssetPreview(
                asset, description=f"{asset.size:,} bytes; metadata preview"
            )
        stat = asset.path.stat()
        if (stat.st_size, stat.st_mtime_ns) != (asset.size, asset.modified_ns):
            return AssetPreview(
                asset, message="Asset changed while decoding. Retry preview."
            )
        return result
    except Exception as error:
        return AssetPreview(
            asset,
            message=(
                f"Cannot preview {asset.path.name}: {error}. Retry or map another file."
            ),
        )
