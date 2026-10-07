"""Ambiguous/stale associations never move boxes onto another source row."""

import json
from dataclasses import replace
from pathlib import Path
from threading import Event
from unittest.mock import patch

import numpy as np
import polars as pl
import pytest
from PIL import Image

from datelier.core.dataset import Dataset, SourceReference
from datelier.inspection.annotations.association_types import PreparedAnnotations
from datelier.inspection.annotations.prepare import prepare_annotations
from datelier.inspection.annotations.settings import (
    AnnotationSettings,
    AnnotationSource,
    ImageAssociationMapping,
    ImageMatch,
)
from datelier.inspection.annotations.types import AnnotationCatalog, AnnotationFormat
from datelier.inspection.arrays.mapping import ArrayLayout, ArrayRecordMapping
from datelier.inspection.images.profile_types import ImageProgress
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.annotations.loading import load_annotations
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.storage import ArrayStore


def table(root: Path) -> Dataset:
    for folder, orientation in (("a", 1), ("b", 6)):
        (root / folder).mkdir()
        image = Image.new("RGB", (100, 80))
        exif = image.getexif()
        exif[274] = orientation
        image.save(root / folder / "scene.png", exif=exif)
    path = root / "records.csv"
    path.write_text("image,key,label\na/scene.png,a/scene,2\nb/scene.png,b/scene,1\n")
    stat = path.stat()
    return Dataset.from_source(
        pl.DataFrame(
            {
                "image": ["a/scene.png", "b/scene.png"],
                "key": ["a/scene", "b/scene"],
                "label": [2, 1],
            }
        ),
        SourceReference(path, stat.st_size, stat.st_mtime_ns),
    )


def voc(path: Path, *, filename: str = "scene.png", width: int = 100) -> None:
    path.write_text(
        f"<annotation><filename>{filename}</filename><size><width>{width}</width><height>80</height></size><object><name>cat</name><bndbox><xmin>11</xmin><ymin>21</ymin><xmax>60</xmax><ymax>50</ymax></bndbox></object></annotation>"
    )


def prepare(
    dataset: Dataset,
    source: AnnotationSource,
    *,
    file_id: str = "file",
    view_name: str = "records",
) -> PreparedAnnotations:
    return prepare_annotations(
        dataset,
        file_id,
        view_name,
        AnnotationSettings("image", (source,)),
        ReferenceSettings(),
        None,
        Event(),
        ImageProgress(),
    )


def test_ambiguous_filenames_require_mapping_and_sort_retains_original_row(
    tmp_path: Path,
) -> None:
    data = table(tmp_path)
    path = tmp_path / "boxes.xml"
    voc(path)
    source = AnnotationSource("truth", str(path))
    initial = prepare(data, source).sources[0]
    assert initial.images[0].status == "Ambiguous" and initial.images[0].candidates == (
        0,
        1,
    )
    assert not initial.boxes and not initial.error
    source = replace(source, mappings=(ImageAssociationMapping("scene.png", 1),))
    sorted_data = data.with_rows(data.table.reverse(), data.row_ids.reverse())
    with patch.object(
        Image.Image, "load", side_effect=AssertionError("association decoded pixels")
    ):
        prepared = prepare(sorted_data, source)
        active = prepared.sources[0]
    assert active.images[0].status == "Ready" and len(active.boxes) == 1
    assert prepared.by_image == {active.boxes[0].origin: active.boxes}
    pin = active.recipe.mappings[0].expected_key
    assert pin is not None and "b/scene.png" in pin
    box = active.boxes[0]
    assert (
        box.origin.row_id == 1
        and box.origin.file_id == "file"
        and box.origin.view_name == "records"
    )
    assert box.box.xyxy == (10, 20, 60, 50) and box.oriented == (30, 10, 60, 60)
    assert sorted_data.table["label"][0] == 1
    filtered = data.with_rows(data.table.head(1), data.row_ids.head(1))
    unavailable = prepare(filtered, active.recipe).sources[0]
    assert (
        unavailable.images[0].status == "Mapped row unavailable"
        and not unavailable.boxes
    )


def test_expected_key_change_and_equal_rows_in_other_files_cannot_share_boxes(
    tmp_path: Path,
) -> None:
    data = table(tmp_path)
    path = tmp_path / "boxes.xml"
    voc(path)
    source = AnnotationSource(
        "truth", str(path), mappings=(ImageAssociationMapping("scene.png", 0),)
    )
    a = prepare(data, source, file_id="first").sources[0]
    b = prepare(data, source, file_id="second").sources[0]
    assert a.boxes[0].origin.row_id == b.boxes[0].origin.row_id == 0
    assert a.boxes[0].identity != b.boxes[0].identity
    changed = data.with_rows(
        data.table.with_columns(
            pl.Series("image", ["another/scene.png", "b/scene.png"])
        ),
        data.row_ids,
    )
    result = prepare(changed, a.recipe).sources[0]
    assert result.images[0].status == "Mapped key changed" and not result.boxes


def test_resolved_path_and_key_column_keep_known_dimensions_and_diagnostics(
    tmp_path: Path,
) -> None:
    data = table(tmp_path)
    path = tmp_path / "boxes.xml"
    voc(path, filename="a/scene.png", width=99)
    source = AnnotationSource("truth", str(path), match=ImageMatch.PATH, image_root=".")
    result = prepare(data, source).sources[0]
    assert not result.error and result.images[0].dimensions == (100, 80)
    assert result.boxes[0].origin.row_id == 0 and result.boxes[0].box.diagnostics
    root = tmp_path / "labels"
    for folder in ("a", "b"):
        (root / folder).mkdir(parents=True)
        (root / folder / "scene.txt").write_text("0 0.35 0.4375 0.5 0.375\n")
    (root / "broken.txt").write_text("broken data")
    keys = replace(
        source,
        path=str(root),
        format=AnnotationFormat.YOLO,
        match=ImageMatch.COLUMN,
        key_column="key",
    )
    result = prepare(data, keys).sources[0]
    assert len(result.boxes) == 2 and {box.origin.row_id for box in result.boxes} == {
        0,
        1,
    }
    assert result.catalog is not None and {
        image.key for image in result.catalog.images
    } == {"a/scene", "b/scene", "broken"}
    assert result.issues and any(image.status == "No match" for image in result.images)


def test_missing_and_corrupt_matched_images_are_not_reassigned(tmp_path: Path) -> None:
    data = table(tmp_path)
    path = tmp_path / "boxes.xml"
    voc(path, filename="a/scene.png")
    source = AnnotationSource("truth", str(path), match=ImageMatch.PATH)
    (tmp_path / "a/scene.png").write_bytes(b"corrupt")
    result = prepare(data, source).sources[0]
    assert result.images[0].status == "Image error" and not result.boxes
    source = replace(
        source,
        match=ImageMatch.FILENAME,
        mappings=(ImageAssociationMapping("a/scene.png", 0),),
    )
    (tmp_path / "a/scene.png").unlink()
    result = prepare(data, source).sources[0]
    assert result.images[0].status == "Image error" and result.images[0].candidates == (
        0,
    )


def test_multiple_sources_preserve_valid_source_when_another_is_unreadable(
    tmp_path: Path,
) -> None:
    data = table(tmp_path)
    path = tmp_path / "boxes.xml"
    voc(path, filename="a/scene.png")
    first = AnnotationSource("valid", str(path), match=ImageMatch.PATH)
    second = AnnotationSource("missing", str(tmp_path / "missing.xml"))
    settings = AnnotationSettings("image", (first, second))
    result = prepare_annotations(
        data, "f", "v", settings, ReferenceSettings(), None, Event(), ImageProgress()
    )
    assert len(result.sources[0].boxes) == 1 and not result.sources[0].error
    assert result.sources[1].error and not result.sources[1].boxes
    stop = Event()
    stop.set()
    from concurrent.futures import CancelledError

    with pytest.raises(CancelledError):
        load_annotations(first, stop)


def test_coco_ids_associate_mapped_arrays_without_extracting_payloads(
    tmp_path: Path,
) -> None:
    source = tmp_path / "images.npz"
    np.savez_compressed(source, images=np.zeros((2, 80, 100, 3), dtype=np.uint8))
    catalog = inspect_arrays(source)
    mapping = ArrayRecordMapping(
        "images", layout=ArrayLayout.IMAGE, display_axes=(1, 2), channel_axis=3
    )
    data = Dataset.from_source(
        pl.DataFrame({"record_index": [0, 1], "label": [9, 1]}), catalog.source
    )
    data = data.with_rows(data.table.reverse(), data.row_ids.reverse())
    annotations = tmp_path / "coco.json"
    annotations.write_text(
        json.dumps(
            {
                "images": [
                    {"id": 0, "file_name": "unused.png", "width": 100, "height": 80}
                ],
                "categories": [{"id": 9, "name": "cat"}],
                "annotations": [
                    {
                        "id": 7,
                        "image_id": 0,
                        "category_id": 99,
                        "bbox": [10, 20, 50, 30],
                    }
                ],
            }
        )
    )
    recipe = AnnotationSource(
        "truth",
        str(annotations),
        format=AnnotationFormat.COCO,
        match=ImageMatch.COLUMN,
        key_column="record_index",
    )
    with patch.object(
        ArrayStore,
        "open_member",
        side_effect=AssertionError("association extracted array"),
    ):
        result = prepare_annotations(
            data,
            "arrays",
            "records",
            AnnotationSettings("images", (recipe,)),
            ReferenceSettings(),
            None,
            Event(),
            ImageProgress(),
            catalog,
            mapping,
        )
    active = result.sources[0]
    assert not active.error and len(active.boxes) == 1
    assert {item.id for item in result.overlay_classes["truth"]} == {9, 99}
    assert active.boxes[0].box.record.class_id == 99 and active.boxes[0].box.diagnostics
    assert active.boxes[0].origin.row_id == 0 and active.boxes[0].box.xyxy == (
        10,
        20,
        60,
        50,
    )
    assert (
        active.images[0].locator is not None
        and active.images[0].locator.source_index == 0
    )


def test_source_changed_after_association_retires_only_its_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = table(tmp_path)
    first_path, second_path = tmp_path / "a.xml", tmp_path / "b.xml"
    voc(first_path, filename="a/scene.png")
    voc(second_path, filename="b/scene.png")
    first = AnnotationSource("first", str(first_path), match=ImageMatch.PATH)
    second = AnnotationSource("second", str(second_path), match=ImageMatch.PATH)

    def changed(source: AnnotationSource, stop: Event) -> AnnotationCatalog:
        if source.id == "second":
            first_path.write_text("external edit")
        return load_annotations(source, stop)

    monkeypatch.setattr(
        "datelier.inspection.annotations.prepare.load_annotations", changed
    )
    result = prepare_annotations(
        data,
        "f",
        "v",
        AnnotationSettings("image", (first, second)),
        ReferenceSettings(),
        None,
        Event(),
        ImageProgress(),
    )
    assert result.sources[0].error and not result.sources[0].boxes
    assert not result.sources[1].error and len(result.sources[1].boxes) == 1
    assert result.sources[1].boxes[0].origin.row_id == 1
