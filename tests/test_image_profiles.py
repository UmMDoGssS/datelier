"""Known colors/dimensions, exact counts, seeded sampling and source preservation."""

from dataclasses import replace
from pathlib import Path
from threading import Event

import numpy as np
import polars as pl
import pytest
from PIL import Image

from datelier.core import Dataset, SourceReference
from datelier.inspection.arrays import ArrayLayout, ArrayRecordMapping
from datelier.inspection.images.decoding import ImageStore
from datelier.inspection.images.profiles import (
    ChannelKey,
    ImageProfile,
    ImageProfileSettings,
    ImageProgress,
    ImageScope,
    ImageScopeMode,
    PixelScope,
)
from datelier.inspection.images.profiles.prepare import (
    finish_image_profile,
    image_positions,
    prepare_image_profile,
)
from datelier.inspection.images.profiles.scan import scan_image_profile
from datelier.inspection.references import ReferenceSettings
from datelier.inspection.references.index import ReferenceIndex
from datelier.io.arrays import ArrayStore
from datelier.io.arrays.metadata import inspect_arrays


def dataset(root: Path, references: list[str | None]) -> Dataset:
    source = root / "source.csv"
    source.write_text("image\n")
    stat = source.stat()
    return Dataset.from_source(
        pl.DataFrame({"image": references}, schema_overrides={"image": pl.String}),
        SourceReference(source, stat.st_size, stat.st_mtime_ns),
    )


def profile(
    table: Dataset,
    settings: ImageProfileSettings | None = None,
    selection: tuple[int, ...] = (),
    index: ReferenceIndex | None = None,
) -> ImageProfile:
    arrays = ArrayStore()
    try:
        return prepare_image_profile(
            table,
            "file",
            "records",
            settings or ImageProfileSettings("image"),
            selection,
            ReferenceSettings(),
            index,
            arrays,
            Event(),
            ImageProgress(),
        )
    finally:
        arrays.close()


def test_exact_mixed_images_dimensions_weighted_channels_and_failure_counts(
    tmp_path: Path,
) -> None:
    Image.fromarray(np.array([[0, 100], [200, 255]], dtype=np.uint8)).save(
        tmp_path / "gray.png"
    )
    Image.new("RGB", (3, 2), (10, 20, 30)).save(tmp_path / "rgb-a.png")
    Image.new("RGB", (1, 2), (50, 60, 70)).save(tmp_path / "rgb-b.png")
    Image.new("RGBA", (2, 1), (40, 80, 120, 64)).save(tmp_path / "rgba.png")
    (tmp_path / "corrupt.png").write_bytes(b"invalid")
    table = dataset(
        tmp_path,
        [
            "gray.png",
            "rgb-a.png",
            "rgb-b.png",
            "rgba.png",
            "missing.png",
            "corrupt.png",
            None,
        ],
    )
    original = {path: path.read_bytes() for path in tmp_path.iterdir()}
    result = profile(table, ImageProfileSettings("image", bins=4))
    assert (result.ready, result.nulls, result.unresolved, result.failures) == (
        4,
        1,
        1,
        1,
    )
    assert (
        result.total_pixels == result.profiled_pixels == 14
        and not result.sampled_pixels
    )
    assert result.records["row_id"].to_list() == list(range(7))
    assert result.records["width"].to_list()[:4] == [2, 3, 1, 2]
    assert result.records["aspect_ratio"].to_list()[:4] == [1, 1.5, 0.5, 2]
    rgb_r = next(
        s for s in result.summaries if s.key.mode == "RGB" and s.key.name == "R"
    )
    assert rgb_r.mean == 20 and rgb_r.finite == 8
    assert rgb_r.stddev == pytest.approx(np.std([10] * 6 + [50] * 2))
    hist = next(h for h in result.channels if "RGB · R ·" in h.label)
    assert hist.counts.tolist() == [6, 0, 0, 2]
    alpha = next(s for s in result.summaries if s.key.name == "A")
    assert alpha.mean == alpha.minimum == alpha.maximum == 64
    assert all(chart.counts.sum() == 4 for chart in result.dimensions)
    assert "missing" in result.records["diagnostic"][4]
    assert "identify image" in result.records["diagnostic"][5]
    assert (
        result.file_id == "file"
        and result.view_name == "records"
        and result.revision == table.revision
    )
    assert all(path.read_bytes() == content for path, content in original.items())


def test_orientation_and_float_nonfinite_statistics_ignore_display_scales(
    tmp_path: Path,
) -> None:
    raw = np.array([[-5.0, 0.0, np.nan], [5.0, np.inf, -np.inf]], dtype=np.float32)
    image = Image.fromarray(raw)
    exif = image.getexif()
    exif[274] = 6
    image.save(tmp_path / "values.tiff", exif=exif)
    result = profile(dataset(tmp_path, ["values.tiff"]))
    assert result.records["width"][0] == 2 and result.records["height"][0] == 3
    summary = result.summaries[0]
    assert summary.finite == summary.nonfinite == 3
    assert summary.minimum == -5 and summary.maximum == 5 and summary.mean == 0
    assert summary.stddev == pytest.approx(np.std([-5.0, 0.0, 5.0]))
    assert result.channels[0].counts.sum() == 3


def test_seeded_record_and_pixel_sampling_survives_sort_and_selection(
    tmp_path: Path,
) -> None:
    values = np.arange(100, dtype=np.uint8).reshape(10, 10)
    Image.fromarray(values).save(tmp_path / "values.png")
    table = dataset(tmp_path, ["values.png"] * 8)
    settings = ImageProfileSettings(
        "image",
        scope=ImageScope(ImageScopeMode.RANDOM, count=3, seed=7),
        pixels=PixelScope.SAMPLE,
        pixel_count=12,
        pixel_seed=11,
    )
    first = profile(table, settings)
    reordered = table.with_rows(table.table.reverse(), table.row_ids.reverse())
    second = profile(reordered, settings)
    assert set(first.records["row_id"]) == set(second.records["row_id"])
    assert (
        first.profiled_pixels == 36
        and first.total_pixels == 300
        and first.sampled_pixels
    )
    np.testing.assert_array_equal(first.channels[0].counts, second.channels[0].counts)
    for row in first.channel_records.iter_rows(named=True):
        row_id = row["row_id"]
        chosen = np.random.default_rng(np.random.SeedSequence([11, row_id])).choice(
            100, 12, replace=False
        )
        assert row["mean"] == pytest.approx(values.ravel()[chosen].mean())
    selected = profile(
        reordered,
        replace(settings, scope=ImageScope(ImageScopeMode.SELECTION)),
        (2, 6, 100),
    )
    assert selected.records["row_id"].to_list() == [6, 2]


@pytest.mark.parametrize("channels_first", [False, True])
def test_mapped_image_array_profiles_keep_supporting_record_identity(
    tmp_path: Path, channels_first: bool
) -> None:
    nhwc = np.arange(2 * 3 * 4 * 3, dtype=np.uint16).reshape(2, 3, 4, 3)
    path = tmp_path / "values.npz"
    np.savez_compressed(
        path,
        pixels=nhwc.transpose(0, 3, 1, 2) if channels_first else nhwc,
        unselected=np.ones((100, 100)),
    )
    original = path.read_bytes()
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping(
        "pixels",
        layout=ArrayLayout.IMAGE,
        display_axes=(2, 3) if channels_first else (1, 2),
        channel_axis=1 if channels_first else 3,
    )
    table = dataset(tmp_path, [None, None])
    table = table.with_rows(table.table.reverse(), table.row_ids.reverse())
    arrays = ArrayStore(retained_bytes=0)
    try:
        result = prepare_image_profile(
            table,
            "array",
            "mapped",
            ImageProfileSettings(
                "pixels", scope=ImageScope(ImageScopeMode.RANGE, count=1)
            ),
            (),
            ReferenceSettings(),
            None,
            arrays,
            Event(),
            ImageProgress(),
            catalog,
            mapping,
        )
        assert result.records["row_id"].to_list() == [1]
        assert result.records["profiled_pixels"][0] == 12
        assert (
            next(s for s in result.summaries if s.key.name == "R").mean
            == nhwc[1, :, :, 0].mean()
        )
        assert arrays.extractions == 1 and arrays.stored_bytes == 0
        assert path.read_bytes() == original
    finally:
        arrays.close()


def test_empty_null_and_ambiguous_collections_keep_diagnostics(tmp_path: Path) -> None:
    empty = profile(dataset(tmp_path, []))
    assert empty.ready == empty.total_pixels == 0 and empty.records.is_empty()
    assert all(chart.counts.sum() == 0 for chart in empty.dimensions)
    first, second = tmp_path / "a.png", tmp_path / "b.png"
    Image.new("L", (1, 1)).save(first)
    Image.new("L", (1, 1)).save(second)
    index = ReferenceIndex({}, {"duplicate": (first, second)})
    result = profile(dataset(tmp_path, [None, "duplicate"]), index=index)
    assert result.nulls == result.unresolved == 1
    assert "Ambiguous" in result.records["diagnostic"][1]


@pytest.mark.parametrize("all_nonfinite", [False, True])
def test_large_integer_and_nonfinite_array_statistics_keep_exact_bounds(
    tmp_path: Path, all_nonfinite: bool
) -> None:
    values = (
        np.array([[[np.nan, np.inf, -np.inf]]], dtype=np.float64)
        if all_nonfinite
        else np.array([[[2**64 - 4, 2**64 - 2]]], dtype=np.uint64)
    )
    path = tmp_path / "values.npy"
    np.save(path, values)
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping("$", layout=ArrayLayout.IMAGE, display_axes=(1, 2))
    arrays = ArrayStore()
    try:
        result = prepare_image_profile(
            dataset(tmp_path, [None]),
            "array",
            "mapped",
            ImageProfileSettings("$", bins=4),
            (),
            ReferenceSettings(),
            None,
            arrays,
            Event(),
            ImageProgress(),
            catalog,
            mapping,
        )
        summary = result.summaries[0]
        if all_nonfinite:
            assert summary.finite == 0 and summary.nonfinite == 3
            assert summary.minimum is summary.mean is summary.stddev is None
            assert result.channels[0].counts.sum() == 0
        else:
            assert summary.minimum == 2**64 - 4 and summary.maximum == 2**64 - 2
            assert summary.stddev == 1
            assert result.channels[0].scaled
            assert result.channels[0].counts.tolist() == [1, 0, 0, 1]
    finally:
        arrays.close()


def test_changed_image_between_statistics_and_histograms_rejects_the_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datelier.inspection.images.profiles.records import (
        ProfileRecord,
        profile_record,
    )
    from datelier.inspection.images.types import ImageLocator, ImageMetadata

    path = tmp_path / "image.png"
    Image.new("RGB", (2, 3), (1, 2, 3)).save(path)
    temporary: list[Path] = []

    def changed(
        locator: ImageLocator,
        metadata: ImageMetadata,
        settings: ImageProfileSettings,
        images: ImageStore,
        arrays: ArrayStore,
        stop: Event,
    ) -> ProfileRecord:
        record = profile_record(locator, metadata, settings, images, arrays, stop)
        assert images.temporary_path is not None
        temporary.append(images.temporary_path)
        Image.new("RGB", (3, 2), (4, 5, 6)).save(path)
        return record

    monkeypatch.setattr(
        "datelier.inspection.images.profiles.scan.profile_record", changed
    )
    with pytest.raises(ValueError, match="changed"):
        profile(dataset(tmp_path, ["image.png"]))
    assert temporary and not temporary[0].exists()


def test_shared_physical_bins_preserve_source_statistics_and_row_identity(
    tmp_path: Path,
) -> None:
    Image.new("RGB", (3, 2), (20, 30, 40)).save(tmp_path / "image.png")
    table = dataset(tmp_path, ["image.png"])
    settings = ImageProfileSettings("image", bins=4)
    arrays, images = ArrayStore(), ImageStore(retained_bytes=0)
    try:
        scan = scan_image_profile(
            table,
            "file",
            "records",
            settings,
            image_positions(table, settings, ()),
            ReferenceSettings(),
            None,
            images,
            arrays,
            Event(),
            ImageProgress(),
        )
        key = ChannelKey("RGB", "R", "|u1")
        width_key = ChannelKey("Dimensions", "Width", "<u8")
        shared = {key: (0, 100), width_key: (1, 5)}
        result = finish_image_profile(
            scan, images, arrays, Event(), ImageProgress(), shared
        )
        summary = next(item for item in result.summaries if item.key == key)
        assert (summary.minimum, summary.maximum, summary.mean) == (20, 20, 20.0)
        chart = result.channels[0]
        assert chart.edges.tolist() == [0.0, 25.0, 50.0, 75.0, 100.0]
        assert chart.counts.tolist() == [6.0, 0.0, 0.0, 0.0]
        assert result.dimensions[0].edges.tolist() == [1.0, 2.0, 3.0, 4.0, 5.0]
        assert result.dimensions[0].counts.tolist() == [0.0, 0.0, 1.0, 0.0]
        assert result.records["row_id"].to_list() == [0]
        assert result.file_id == "file" and result.view_name == "records"
        assert result.total_pixels == 6 and result.profiled_pixels == 6
        assert images.stored_bytes == 0 and arrays.extractions == 0
    finally:
        arrays.close()
        images.cleanup()
