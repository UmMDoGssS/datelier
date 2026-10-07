"""Raw scalar values, slices and identities stay independent of display choices."""

import hashlib
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
import polars as pl
import pytest
from numpy.typing import NDArray

from datelier.core.dataset import Dataset
from datelier.inspection.arrays.mapping import ArrayLayout, ArrayRecordMapping
from datelier.inspection.arrays.slices import SliceSettings, prepare_slice
from datelier.inspection.heatmaps import Colormap, normalize, ramp_colors
from datelier.inspection.images.prepare import display_pixels, prepare_window
from datelier.inspection.images.sources import image_metadata, locate_image
from datelier.inspection.images.storage import ImageStore
from datelier.inspection.images.types import ImageDisplay, ImageMetadata, ImageWindow
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.storage import ArrayStore
from datelier.workspace.codec import decode_record, encode


@pytest.mark.parametrize(
    "raw,expected,bounds",
    [
        (np.array([-10, 0, 10], dtype=np.int16), [0, 0.5, 1], (-10, 10)),
        (np.array([-1e308, 0, 1e308]), [0, 0.5, 1], (-1e308, 1e308)),
        (np.full(3, -5.0), [0.5, 0.5, 0.5], (-5, -5)),
        (
            np.array([2**64 - 3, 2**64 - 2, 2**64 - 1], dtype=np.uint64),
            [0, 0.5, 1],
            (2**64 - 3, 2**64 - 1),
        ),
    ],
)
def test_normalization_preserves_physical_bounds_and_raw_values(
    raw: NDArray[np.generic],
    expected: list[float],
    bounds: tuple[int | float, int | float],
) -> None:
    before = raw.copy()
    result = normalize(raw)
    assert result.bounds == result.display_range == bounds
    np.testing.assert_array_equal(result.colors, expected)
    np.testing.assert_array_equal(raw, before)
    assert not result.colors.flags.writeable
    if raw.dtype.kind in "iu":
        assert result.bounds is not None and isinstance(result.bounds[0], int)


def test_nonfinite_marks_and_manual_clipping_are_display_only() -> None:
    raw = np.array([[-10, 0, 10], [np.nan, np.inf, -np.inf]])
    original = normalize(raw)
    changed = normalize(raw, (-5, 5))
    assert original.bounds == changed.bounds == (-10, 10)
    assert changed.display_range == (-5, 5) and changed.nonfinite == 3
    for colormap in Colormap:
        rgba = ramp_colors(changed.colors, colormap)
        np.testing.assert_array_equal(rgba[1], np.tile([255, 0, 255, 255], (3, 1)))
        assert not rgba.flags.writeable
    assert np.isinf(raw[1, 1]) and np.isneginf(raw[1, 2])
    empty = normalize(raw[1])
    assert empty.bounds is None and empty.display_range is None and empty.nonfinite == 3
    np.testing.assert_array_equal(
        ramp_colors(empty.colors, Colormap.GRAY), np.tile([255, 0, 255, 255], (3, 1))
    )
    for bounds in ((0, 0), (1, -1), (np.nan, 1), (0, np.inf)):
        with pytest.raises(ValueError, match="range"):
            normalize(raw, bounds)


def test_selected_encoded_channel_excludes_other_channels_nonfinite() -> None:
    raw = np.array([[[0.5, np.nan, 1], [0.25, 0.5, np.inf]]])
    metadata = ImageMetadata(2, 1, 2, 1, ("R", "G", "B"), raw.dtype, "RGB")
    rgba, nonfinite = display_pixels(raw, metadata, ImageDisplay(channel=0))
    assert nonfinite == 0
    np.testing.assert_array_equal(rgba[0, :, 0], [128, 64])
    _, composite_nonfinite = display_pixels(raw, metadata, ImageDisplay())
    assert composite_nonfinite == 2


def test_mapped_channel_slice_and_sort_preserve_source_provenance(
    tmp_path: Path,
) -> None:
    # N, depth, C, W, H: preserve chosen display-axis order without an HWC copy.
    raw = np.arange(2 * 3 * 5 * 4 * 6, dtype=np.int16).reshape(2, 3, 5, 4, 6)
    path = tmp_path / "volume.npz"
    np.savez_compressed(path, heat=raw, untouched=np.zeros((2, 4)))
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping(
        "heat", layout=ArrayLayout.HEATMAP, display_axes=(4, 3), channel_axis=2
    )
    table = Dataset.from_source(pl.DataFrame({"record_index": [0, 1]}), catalog.source)
    table = table.with_rows(table.table.reverse(), table.row_ids.reverse())
    locator = locate_image(
        table, "file", "volume", "heat", 0, ReferenceSettings(), None, catalog, mapping
    )
    metadata = image_metadata(locator)
    assert metadata.mode == "Numeric" and metadata.count == 5
    assert locator.origin.row_id == locator.source_index == 1
    images, arrays = ImageStore(), ArrayStore(retained_bytes=1)
    try:
        display = ImageDisplay(channel=3, fixed=(0, 2, 0, 0, 0))
        result = prepare_window(
            locator, metadata, ImageWindow(1, 2, 2, 3), display, images, arrays
        )
        expected = raw[1, 2, 3, 1:3, 2:5].T
        np.testing.assert_array_equal(result.raw, expected)
        assert result.pixel(1, 2) == (int(raw[1, 2, 3, 1, 2]),)
        assert result.finite_range == (int(expected.min()), int(expected.max()))
        altered = prepare_window(
            locator,
            metadata,
            result.window,
            replace(display, value_range=(0, 1000), colormap=Colormap.PURPLE_GOLD),
            images,
            arrays,
        )
        np.testing.assert_array_equal(altered.raw, result.raw)
        assert altered.finite_range == result.finite_range
        assert altered.display_range == (0, 1000)
        assert arrays.stored_bytes == images.stored_bytes == 0
        for bad in (
            replace(display, channel=5),
            replace(display, fixed=(0,)),
            replace(display, fixed=(0, 3, 0, 0, 0)),
        ):
            with pytest.raises(ValueError):
                prepare_window(locator, metadata, result.window, bad, images, arrays)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    finally:
        images.cleanup()
        arrays.close()


def test_large_channel_axis_opens_metadata_and_reads_only_one_scalar(
    tmp_path: Path,
) -> None:
    path = tmp_path / "wide.npy"
    raw = np.lib.format.open_memmap(
        path, mode="w+", dtype=np.float64, shape=(1, 1, 1, 2_000_000)
    )
    raw[0, 0, 0, -1] = -37
    raw.flush()
    del raw
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping(
        "$", layout=ArrayLayout.HEATMAP, display_axes=(1, 2), channel_axis=3
    )
    table = Dataset.from_source(pl.DataFrame({"record_index": [0]}), catalog.source)
    locator = locate_image(
        table, "f", "v", "$", 0, ReferenceSettings(), None, catalog, mapping
    )
    with patch.object(
        ArrayStore, "open_member", side_effect=AssertionError("metadata read pixels")
    ):
        metadata = image_metadata(locator)
    assert metadata.count == 2_000_000 and len(metadata.channels) == 1
    arrays, images = ArrayStore(), ImageStore()
    try:
        result = prepare_window(
            locator,
            metadata,
            ImageWindow(),
            ImageDisplay(channel=1_999_999),
            images,
            arrays,
            1024 * 1024,
        )
        assert result.raw.shape == (1, 1) and result.pixel(0, 0) == (-37.0,)
        assert result.retained_bytes == 12 and result.finite_range == (-37, -37)
    finally:
        arrays.close()
        images.cleanup()


def test_slice_display_and_saved_recipes_preserve_statistics(tmp_path: Path) -> None:
    path = tmp_path / "values.npy"
    raw = np.array([[-3.0, 1, 7], [np.nan, np.inf, -np.inf]])
    np.save(path, raw)
    catalog, arrays = inspect_arrays(path), ArrayStore()
    try:
        settings = SliceSettings()
        first = prepare_slice(arrays, catalog, settings)
        settings = replace(settings, value_range=(-10, 10), colormap=Colormap.BLUE_RED)
        second = prepare_slice(arrays, catalog, settings)
        assert first.finite_range == second.finite_range == (-3, 7)
        assert first.nonfinite == second.nonfinite == 3
        np.testing.assert_array_equal(first.raw, second.raw)
        np.testing.assert_array_equal(first.numeric, second.numeric)
        assert first.colors is not None and second.colors is not None
        assert not np.array_equal(first.colors, second.colors, equal_nan=True)
        assert decode_record(SliceSettings, encode(settings)) == settings
        display = ImageDisplay(1, (-10, 10), Colormap.BLUE_RED, (0, 2, 0))
        assert decode_record(ImageDisplay, encode(display)) == display
        legacy = encode(ImageDisplay())
        assert isinstance(legacy, dict)
        legacy.pop("colormap")
        legacy.pop("fixed")
        assert decode_record(ImageDisplay, legacy) == ImageDisplay()
    finally:
        arrays.close()


def test_numeric_window_limits_retention_without_losing_original_access(
    tmp_path: Path,
) -> None:
    path = tmp_path / "large.npy"
    raw = np.lib.format.open_memmap(
        path, mode="w+", dtype=np.float64, shape=(1, 2048, 3072)
    )
    values = np.arange(3072, dtype=np.float64)
    for row in range(2048):
        raw[0, row] = values - row
    raw.flush()
    del raw
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping("$", layout=ArrayLayout.HEATMAP, display_axes=(1, 2))
    table = Dataset.from_source(pl.DataFrame({"record_index": [0]}), catalog.source)
    locator = locate_image(
        table, "f", "v", "$", 0, ReferenceSettings(), None, catalog, mapping
    )
    images, arrays = ImageStore(), ArrayStore(retained_bytes=1)
    try:
        metadata = image_metadata(locator)
        window = prepare_window(
            locator,
            metadata,
            ImageWindow(1500, 900, 1024, 1024),
            ImageDisplay(),
            images,
            arrays,
            1024 * 1024,
        )
        assert window.limited and window.window.step == 4
        assert window.retained_bytes <= 1024 * 1024
        assert window.pixel(1500, 900) == (600.0,)
        assert window.pixel(1501, 900) is None
        exact = prepare_window(
            locator,
            metadata,
            ImageWindow(1501, 900, 1, 1),
            ImageDisplay(),
            images,
            arrays,
            1024 * 1024,
        )
        assert exact.pixel(1501, 900) == (601.0,) and not exact.limited
        assert images.decodes == arrays.extractions == arrays.stored_bytes == 0
    finally:
        arrays.close()
        images.cleanup()
