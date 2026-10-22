"""Exact original-pixel windows with independently prepared RGBA display buffers."""

from collections.abc import Callable
from dataclasses import replace
from math import ceil

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from datelier.inspection.heatmaps import normalize, ramp_colors
from datelier.inspection.images.decoding.storage import ImageStore
from datelier.inspection.images.geometry import orient_array
from datelier.inspection.images.types import (
    ImageDisplay,
    ImageLocator,
    ImageMetadata,
    ImageWindow,
    PreparedImage,
)
from datelier.io.arrays import ArrayStore


def bounded_window(
    window: ImageWindow, metadata: ImageMetadata, cpu_bytes: int
) -> ImageWindow:
    window.validate()
    if cpu_bytes < 1024 * 1024:
        raise ValueError("Image CPU retention requires at least 1 MiB")
    left, top = (
        min(window.left, metadata.width - 1),
        min(window.top, metadata.height - 1),
    )
    width, height = (
        min(window.width, metadata.width - left),
        min(window.height, metadata.height - top),
    )
    count = 1 if metadata.mode == "Numeric" else metadata.count
    per_pixel = metadata.dtype.itemsize * count + 4
    step = max(window.step, ceil(width / 1024), ceil(height / 1024))
    step = max(step, ceil((width * height * per_pixel / cpu_bytes) ** 0.5))
    while ceil(width / step) * ceil(height / step) * per_pixel > cpu_bytes:
        step += 1
    return ImageWindow(left, top, width, height, step)


def default_range(dtype: np.dtype[np.generic]) -> tuple[float, float]:
    if dtype.kind == "b" or dtype.kind == "f":
        return 0.0, 1.0
    info = np.iinfo(dtype.str)
    return float(info.min), float(info.max)


def display_pixels(
    raw: NDArray[np.generic], metadata: ImageMetadata, display: ImageDisplay
) -> tuple[NDArray[np.uint8], int]:
    display.validate()
    if metadata.mode == "Numeric":
        if raw.ndim != 2:
            raise ValueError("Numeric heatmaps require one selected scalar plane")
        values = normalize(raw, display.value_range)
        return ramp_colors(values.colors, display.colormap), values.nonfinite
    channels = raw[:, :, None] if raw.ndim == 2 else raw
    if display.channel is not None and display.channel >= channels.shape[2]:
        raise ValueError("Chosen image channel is unavailable")
    chosen = (
        channels
        if display.channel is None
        else channels[:, :, display.channel : display.channel + 1]
    )
    values = np.asarray(chosen, dtype=np.float64)
    finite = np.isfinite(values)
    nonfinite = int(values.size - np.count_nonzero(finite))
    lo, hi = display.value_range or default_range(raw.dtype)
    scale = max(abs(lo), abs(hi), 1.0)
    normalized = (values / scale - lo / scale) / (hi / scale - lo / scale)
    byte = np.asarray(
        np.rint(np.clip(np.nan_to_num(normalized), 0, 1) * 255), dtype=np.uint8
    )
    rgba = np.full((*raw.shape[:2], 4), 255, dtype=np.uint8)
    if display.channel is not None:
        rgba[:, :, :3] = byte[:, :, :1]
    elif metadata.mode == "CMYK":
        rgba[:, :, :3] = np.asarray(Image.fromarray(byte, "CMYK").convert("RGB"))
    elif byte.shape[2] in (1, 2):
        rgba[:, :, :3] = byte[:, :, :1]
        if byte.shape[2] == 2:
            rgba[:, :, 3] = byte[:, :, 1]
    else:
        rgba[:, :, :3] = byte[:, :, :3]
        if byte.shape[2] == 4:
            rgba[:, :, 3] = byte[:, :, 3]
    rgba[~finite.all(axis=2)] = (255, 0, 255, 255)
    rgba.flags.writeable = False
    return rgba, nonfinite


def prepare_window(
    locator: ImageLocator,
    metadata: ImageMetadata,
    requested: ImageWindow,
    display: ImageDisplay,
    images: ImageStore,
    arrays: ArrayStore,
    cpu_bytes: int = 16 * 1024 * 1024,
    stopped: Callable[[], bool] | None = None,
) -> PreparedImage:
    display = channel_display(metadata, display)
    display.validate()
    if display.channel is not None and display.channel >= metadata.count:
        raise ValueError("Chosen image channel is unavailable")
    window = bounded_window(requested, metadata, cpu_bytes)
    spatial = (
        slice(window.top, window.top + window.height, window.step),
        slice(window.left, window.left + window.width, window.step),
    )
    if locator.asset is not None:
        with images.open_file(locator.asset, stopped) as array:
            oriented = orient_array(array, metadata.orientation)
            raw = oriented[spatial].copy()
    else:
        catalog, mapping = locator.catalog, locator.mapping
        if catalog is None or mapping is None or locator.source_index is None:
            raise ValueError("Image record mapping is unavailable")
        shape = catalog.member(mapping.member).shape
        fixed = (
            display.fixed
            if metadata.mode == "Numeric" and display.fixed
            else mapping.fixed
        )
        if fixed and len(fixed) != len(shape):
            raise ValueError("Heatmap slice rank does not match the array")
        positions = fixed or (0,) * len(shape)
        used_axes = (mapping.record_axis, *mapping.display_axes, mapping.channel_axis)
        if any(
            position >= shape[axis]
            for axis, position in enumerate(positions)
            if axis not in used_axes
        ):
            raise ValueError("Heatmap slice is outside the selected array")
        selectors: list[int | slice] = list(positions)
        selectors[mapping.record_axis] = locator.source_index
        for axis, selector in zip(mapping.display_axes, spatial, strict=True):
            selectors[axis] = selector
        axes = mapping.display_axes
        if mapping.channel_axis is not None:
            if metadata.mode == "Numeric":
                selectors[mapping.channel_axis] = display.channel or 0
            else:
                selectors[mapping.channel_axis] = slice(None)
                axes = (*axes, mapping.channel_axis)
        with arrays.open_member(catalog, mapping.member, stopped) as array:
            selected = np.asarray(array[tuple(selectors)])
            raw = selected.transpose(
                tuple(sorted(axes).index(axis) for axis in axes)
            ).copy()
    raw.flags.writeable = False
    values = normalize(raw, display.value_range) if metadata.mode == "Numeric" else None
    if values is not None:
        rgba, nonfinite = ramp_colors(values.colors, display.colormap), values.nonfinite
    else:
        rgba, nonfinite = display_pixels(raw, metadata, display)
    return PreparedImage(
        locator,
        metadata,
        window,
        display,
        raw,
        rgba,
        nonfinite,
        window != requested,
        values.bounds if values else None,
        values.display_range if values else None,
    )


def channel_display(metadata: ImageMetadata, display: ImageDisplay) -> ImageDisplay:
    """Numeric mappings never silently become encoded RGB."""
    return (
        replace(display, channel=0)
        if metadata.mode == "Numeric" and display.channel is None
        else display
    )
