"""Original-pixel, orientation, mapped-record and worker ownership invariants."""

import struct
from concurrent.futures import CancelledError, ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch

import numpy as np
import polars as pl
import pytest
from PIL import Image, ImageOps

from datelier.core import Dataset, SourceReference
from datelier.inspection.arrays import ArrayLayout, ArrayRecordMapping
from datelier.inspection.images.decoding import ImageStore, prepare_window
from datelier.inspection.images.decoding.sources import image_metadata, locate_image
from datelier.inspection.images.geometry import orient_array, source_pixel
from datelier.inspection.images.jobs import ImageJobs
from datelier.inspection.images.types import ImageDisplay, ImageLocator, ImageWindow
from datelier.inspection.references import ReferenceSettings
from datelier.io.arrays import ArrayStore
from datelier.io.arrays.metadata import inspect_arrays


def dataset(root: Path, paths: list[str | None]) -> Dataset:
    source = root / "source.csv"
    source.write_text("id,image\n")
    stat = source.stat()
    return Dataset.from_source(
        pl.DataFrame(
            {"id": range(len(paths)), "image": paths},
            schema_overrides={"image": pl.String},
        ),
        SourceReference(source, stat.st_size, stat.st_mtime_ns),
    )


def locator(table: Dataset, position: int = 0) -> ImageLocator:
    return locate_image(
        table, "file-a", "records", "image", position, ReferenceSettings(), None
    )


@pytest.mark.parametrize("mode", ["L", "RGB", "RGBA", "I;16", "F", "1", "P"])
def test_file_dimensions_exact_pixels_and_display_preserves_source(
    tmp_path: Path, mode: str
) -> None:
    values = np.arange(6, dtype=np.uint8).reshape(2, 3)
    if mode in ("RGB", "RGBA"):
        values = np.repeat(values[:, :, None], len(mode), axis=2)
    elif mode == "I;16":
        values = values.astype(np.uint16) * 1000
    elif mode == "F":
        values = values.astype(np.float32) / 5
    image = Image.fromarray(values).convert(mode)
    path = tmp_path / "image.tiff"
    image.save(path)
    before = path.read_bytes()
    table = dataset(tmp_path, [path.name])
    origin = locator(table)
    metadata = image_metadata(origin)
    assert (metadata.width, metadata.height) == (3, 2)
    images, arrays = ImageStore(), ArrayStore()
    try:
        prepared = prepare_window(
            origin, metadata, ImageWindow(1, 0, 2, 2), ImageDisplay(), images, arrays
        )
        with Image.open(path) as saved:
            expected = np.asarray(saved.convert("RGBA") if mode == "P" else saved)
        np.testing.assert_array_equal(prepared.raw, expected[:, 1:])
        assert prepared.pixel(1, 0) == tuple(np.atleast_1d(expected[0, 1]).tolist())
        assert prepared.pixel(0, 0) is None
        assert not prepared.raw.flags.writeable and not prepared.rgba.flags.writeable
        alternative = prepare_window(
            origin,
            metadata,
            ImageWindow(1, 0, 2, 2),
            ImageDisplay(channel=0, value_range=(-10, 100)),
            images,
            arrays,
        )
        np.testing.assert_array_equal(alternative.raw, prepared.raw)
        assert images.decodes == 1
        assert path.read_bytes() == before
    finally:
        images.cleanup()
        arrays.close()


@pytest.mark.parametrize("orientation", range(1, 9))
@pytest.mark.parametrize("extension", ["png", "tiff"])
def test_exif_pixels_and_inverse_geometry(
    tmp_path: Path, orientation: int, extension: str
) -> None:
    raw = np.arange(18, dtype=np.uint8).reshape(2, 3, 3)
    image = Image.fromarray(raw)
    exif = image.getexif()
    exif[274] = orientation
    path = tmp_path / f"oriented.{extension}"
    image.save(path, exif=exif)
    origin = locator(dataset(tmp_path, [path.name]))
    metadata = image_metadata(origin)
    with Image.open(path) as saved:
        expected = np.asarray(ImageOps.exif_transpose(saved))
    np.testing.assert_array_equal(orient_array(raw, orientation), expected)
    images, arrays = ImageStore(), ArrayStore()
    try:
        result = prepare_window(
            origin, metadata, ImageWindow(), ImageDisplay(), images, arrays
        )
        np.testing.assert_array_equal(result.raw, expected)
        for y in range(metadata.height):
            for x in range(metadata.width):
                sx, sy = source_pixel(x, y, 3, 2, orientation)
                np.testing.assert_array_equal(result.raw[y, x], raw[sy, sx])
    finally:
        images.cleanup()
        arrays.close()


@pytest.mark.parametrize("channel_axis", [1, 3])
def test_mapped_image_channels_follow_source_rows_after_sort(
    tmp_path: Path, channel_axis: int
) -> None:
    nhwc = np.arange(2 * 3 * 4 * 3, dtype=np.uint8).reshape(2, 3, 4, 3)
    data = nhwc if channel_axis == 3 else nhwc.transpose(0, 3, 1, 2)
    path = tmp_path / "images.npy"
    np.save(path, data)
    catalog = inspect_arrays(path)
    member = catalog.members[0].name
    mapping = ArrayRecordMapping(
        member,
        layout=ArrayLayout.IMAGE,
        display_axes=(1, 2) if channel_axis == 3 else (2, 3),
        channel_axis=channel_axis,
    )
    table = dataset(tmp_path, [None, None])
    sorted_table = table.with_rows(table.table.reverse(), table.row_ids.reverse())
    origin = locate_image(
        sorted_table,
        "file-a",
        "mapped",
        "image",
        0,
        ReferenceSettings(),
        None,
        catalog,
        mapping,
    )
    assert origin.origin.row_id == origin.source_index == 1
    metadata = image_metadata(origin)
    images, arrays = ImageStore(), ArrayStore()
    try:
        result = prepare_window(
            origin, metadata, ImageWindow(), ImageDisplay(channel=1), images, arrays
        )
        np.testing.assert_array_equal(result.raw, nhwc[1])
        np.testing.assert_array_equal(result.rgba[:, :, 0], nhwc[1, :, :, 1])
    finally:
        images.cleanup()
        arrays.close()


def test_cache_limits_preserve_full_image_access_and_cleanup_leases(
    tmp_path: Path,
) -> None:
    path = tmp_path / "large.png"
    Image.new("RGB", (2048, 1536), (7, 8, 9)).save(path)
    origin = locator(dataset(tmp_path, [path.name]))
    metadata = image_metadata(origin)
    images, arrays = ImageStore(retained_bytes=1), ArrayStore()
    result = prepare_window(
        origin,
        metadata,
        ImageWindow(1600, 1000, 1024, 1024),
        ImageDisplay(),
        images,
        arrays,
        1024 * 1024,
    )
    assert result.retained_bytes <= 1024 * 1024 and result.limited
    assert result.pixel(1600, 1000) == (7, 8, 9)
    assert images.stored_bytes == 0
    assert origin.asset is not None
    with pytest.raises(CancelledError), images.open_file(origin.asset) as mapped:
        directory = images.temporary_path
        assert directory is not None
        images.cleanup()
        assert directory.exists() and mapped[0, 0].tolist() == [7, 8, 9]
    assert not directory.exists()
    arrays.close()


def test_null_missing_corrupt_and_changed_assets_are_actionable(tmp_path: Path) -> None:
    table = dataset(tmp_path, [None, "missing.png", "corrupt.png", "good.png"])
    with pytest.raises(ValueError, match="null"):
        locator(table)
    with pytest.raises(ValueError, match="[Mm]issing|[Nn]o|resolve"):
        locator(table, 1)
    (tmp_path / "corrupt.png").write_bytes(b"not an image")
    with pytest.raises(Exception, match="identify image"):
        image_metadata(locator(table, 2))
    Image.new("L", (2, 2)).save(tmp_path / "good.png")
    origin = locator(table, 3)
    (tmp_path / "good.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        image_metadata(origin)


@pytest.mark.parametrize("exif_after_pixels", [False, True])
def test_metadata_does_not_decode_pixels_even_with_late_png_exif(
    tmp_path: Path, exif_after_pixels: bool
) -> None:
    path = tmp_path / "header.png"
    image = Image.new("RGB", (20, 10))
    exif = image.getexif()
    exif[274] = 6
    image.save(path, exif=exif if exif_after_pixels else None)
    if exif_after_pixels:
        content = path.read_bytes()
        chunks: list[bytes] = []
        offset = 8
        while offset < len(content):
            length = struct.unpack(">I", content[offset : offset + 4])[0]
            chunks.append(content[offset : offset + length + 12])
            offset += length + 12
        annotation = next(chunk for chunk in chunks if chunk[4:8] == b"eXIf")
        chunks.remove(annotation)
        chunks.insert(-1, annotation)
        path.write_bytes(content[:8] + b"".join(chunks))
    origin = locator(dataset(tmp_path, [path.name]))
    with patch.object(
        Image.Image, "load", side_effect=AssertionError("metadata decoded pixels")
    ):
        metadata = image_metadata(origin)
    assert (metadata.width, metadata.height) == (
        (10, 20) if exif_after_pixels else (20, 10)
    )


def poll(jobs: ImageJobs) -> None:
    end = monotonic() + 5
    while jobs.busy and monotonic() < end:
        jobs.poll()
        sleep(0.001)
    assert not jobs.busy


def test_job_revision_file_view_and_closure_reject_late_metadata(
    tmp_path: Path,
) -> None:
    path = tmp_path / "image.png"
    Image.new("RGB", (3, 2)).save(path)
    table = dataset(tmp_path, [path.name])
    entered, release = Event(), Event()
    from datelier.inspection.images.decoding.sources import prepare_metadata

    def delayed(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return prepare_metadata(*args, **kwargs)

    with (
        ThreadPoolExecutor(1) as worker,
        patch("datelier.inspection.images.jobs.prepare_metadata", new=delayed),
    ):
        jobs = ImageJobs(worker)
        jobs.sync("file-a", "one", table.revision, ReferenceSettings(), None)
        jobs.request_record(table, "image", 0)
        assert entered.wait(5)
        revision = replace(table.revision)
        jobs.sync("file-b", "two", revision, ReferenceSettings(), None)
        release.set()
        poll(jobs)
        assert jobs.metadata is None and jobs.active is None
        jobs.request_record(replace(table, revision=revision), "image", 0)
        poll(jobs)
        assert jobs.metadata is not None and jobs.metadata[0].origin.file_id == "file-b"
        jobs.close()
        jobs.request_record(table, "image", 0)
        jobs.poll()
        assert jobs.metadata is None and jobs.active is None
