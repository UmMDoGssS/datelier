"""Leased original image grids and bounded exact/seeded pixel batches for workers."""

from collections.abc import Iterator
from concurrent.futures import CancelledError
from contextlib import contextmanager
from threading import Event
from typing import cast

import numpy as np
from numpy.typing import NDArray

from datelier.inspection.images.decoding.storage import ImageStore
from datelier.inspection.images.geometry import orient_array
from datelier.inspection.images.profiles import ImageProfileSettings, PixelScope
from datelier.inspection.images.types import ImageLocator
from datelier.io.arrays import ArrayStore


def check_cancelled(stop: Event) -> None:
    if stop.is_set():
        raise CancelledError("Image collection preparation abandoned")


@contextmanager
def original_pixels(
    locator: ImageLocator,
    orientation: int,
    images: ImageStore,
    arrays: ArrayStore,
    stop: Event,
) -> Iterator[NDArray[np.generic]]:
    check_cancelled(stop)
    if locator.asset is not None:
        with images.open_file(locator.asset, stop.is_set) as raw:
            selected = orient_array(raw, orientation)
            yield selected[:, :, None] if selected.ndim == 2 else selected
    else:
        catalog, mapping = locator.catalog, locator.mapping
        if catalog is None or mapping is None or locator.source_index is None:
            raise ValueError("Image record mapping is unavailable")
        shape = catalog.member(mapping.member).shape
        selectors: list[int | slice] = list(mapping.fixed or (0,) * len(shape))
        selectors[mapping.record_axis] = locator.source_index
        axes = mapping.display_axes
        for axis in axes:
            selectors[axis] = slice(None)
        if mapping.channel_axis is not None:
            selectors[mapping.channel_axis] = slice(None)
            axes = (*axes, mapping.channel_axis)
        with arrays.open_member(catalog, mapping.member, stop.is_set) as raw:
            selected = cast(
                NDArray[np.generic],
                np.asarray(raw[tuple(selectors)]).transpose(
                    tuple(sorted(axes).index(axis) for axis in axes)
                ),
            )
            yield selected[:, :, None] if selected.ndim == 2 else selected
    check_cancelled(stop)


def pixel_batches(
    raw: NDArray[np.generic],
    settings: ImageProfileSettings,
    row_id: int,
    stop: Event,
) -> Iterator[NDArray[np.generic]]:
    height, width, channels = raw.shape
    if settings.pixels == PixelScope.SAMPLE and settings.pixel_count < width * height:
        rng = np.random.default_rng(
            np.random.SeedSequence([settings.pixel_seed, row_id])
        )
        indices = rng.choice(width * height, settings.pixel_count, replace=False)
        for start in range(0, len(indices), 32768):
            check_cancelled(stop)
            chosen = indices[start : start + 32768]
            yield cast(NDArray[np.generic], raw[chosen // width, chosen % width])
            stop.wait(0.001)
    else:
        # Bound noncontiguous NCHW/oriented channel copies by spatial patches,
        # rather than flattening an entire strided image into another array.
        for top in range(0, height, 32):
            for left in range(0, width, 1024):
                check_cancelled(stop)
                yield cast(
                    NDArray[np.generic],
                    raw[top : top + 32, left : left + 1024].reshape(-1, channels),
                )
            stop.wait(0.001)
    check_cancelled(stop)
