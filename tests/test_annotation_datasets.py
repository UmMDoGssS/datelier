"""COCO identity joins and local manifest membership, diagnostics and preservation."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from datelier.inspection.annotations.geometry import pixel_box
from datelier.inspection.images.decoding.sources import file_metadata
from datelier.inspection.images.types import ImageMetadata
from datelier.inspection.references import AssetIdentity
from datelier.io.annotations.manifest_paths import label_path
from datelier.io.annotations.readers import read_coco, read_ultralytics
from datelier.io.annotations.yaml_source import decode_manifest


def coco() -> dict[str, object]:
    return {
        "images": [{"id": 42, "file_name": "scene.png", "width": 100, "height": 80}],
        "categories": [{"id": 9, "name": "cat"}],
        "annotations": [
            {
                "id": 7,
                "image_id": 42,
                "category_id": 9,
                "bbox": [10, 20, 50, 30],
                "score": 0.8,
                "iscrowd": 1,
            }
        ],
    }


def dataset(root: Path) -> Path:
    (root / "images/train").mkdir(parents=True)
    (root / "labels/train").mkdir(parents=True)
    image = Image.new("RGB", (100, 80))
    exif = image.getexif()
    exif[274] = 6
    image.save(root / "images/train/scene.png", exif=exif)
    Image.new("L", (40, 30)).save(root / "images/train/empty.png")
    Image.new("L", (10, 10)).save(root / "images/train/missing.png")
    (root / "labels/train/scene.txt").write_text("0 0.35 0.4375 0.5 0.375\n")
    (root / "labels/train/empty.txt").write_text("")
    manifest = root / "data.yaml"
    manifest.write_text("path: .\ntrain: images/train\nnames: [cat]\n")
    return manifest


def test_coco_sparse_ids_score_crowd_and_original_pixel_coordinates(
    tmp_path: Path,
) -> None:
    path = tmp_path / "annotations.json"
    path.write_text(json.dumps(coco()))
    original = path.read_bytes()
    catalog = read_coco(path)
    assert len(catalog.boxes) == len(catalog.images) == 1 and not catalog.issues
    box = catalog.boxes[0]
    assert catalog.images[0].key == box.image_key == "42"
    assert box.class_id == 9 and box.class_name == "cat" and box.annotation_id == "7"
    assert (
        box.original == (10, 20, 50, 30)
        and box.flags == ("crowd",)
        and box.score == 0.8
    )
    assert pixel_box(box, 100, 80).xyxy == (10, 20, 60, 50)
    assert box.location == "annotations[0]" and box.asset.path == path
    assert path.read_bytes() == original


def test_coco_orphan_duplicate_invalid_and_unknown_class_records_are_visible(
    tmp_path: Path,
) -> None:
    data = coco()
    data["annotations"] = [
        {"id": 1, "image_id": 42, "category_id": 999, "bbox": [0, 0, 1, 1]},
        {"id": 2, "image_id": 999, "category_id": 9, "bbox": [0, 0, 1, 1]},
        {"id": 1, "image_id": 42, "category_id": 9, "bbox": [0, 0, 1, 1]},
        {"id": 3, "image_id": 42, "category_id": 9, "bbox": [1, 2, 3]},
        {"id": 4, "image_id": 42, "category_id": 9, "bbox": [1, 2, -3, 4]},
    ]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    catalog = read_coco(path)
    assert len(catalog.boxes) == 2 and len(catalog.issues) == 3
    assert catalog.boxes[0].class_id == 999 and catalog.boxes[0].diagnostics
    assert (
        catalog.issues[0].image_key == "999" and "Unknown" in catalog.issues[0].message
    )
    assert "Duplicate" in catalog.issues[1].message and catalog.issues[2].original
    with pytest.raises(ValueError, match="positive"):
        pixel_box(catalog.boxes[1], 100, 80)


@pytest.mark.parametrize("field", ["images", "categories"])
def test_coco_duplicate_identity_headers_fail_without_reassignment(
    tmp_path: Path, field: str
) -> None:
    data = coco()
    items = data[field]
    assert isinstance(items, list)
    data[field] = items * 2
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Duplicate"):
        read_coco(path)
    path.write_text('{"images": [], "images": []}')
    with pytest.raises(ValueError, match="Duplicate JSON"):
        read_coco(path)


def test_manifest_header_only_orientation_original_dimensions_and_label_outcomes(
    tmp_path: Path,
) -> None:
    manifest = dataset(tmp_path)
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    with patch.object(
        Image.Image, "load", side_effect=AssertionError("manifest decoded pixels")
    ):
        catalog = read_ultralytics(manifest)
    assert (
        catalog.class_count == 1
        and len(catalog.images) == 3
        and len(catalog.boxes) == 1
    )
    images = {image.key: image for image in catalog.images}
    assert images["images/train/scene.png"].dimensions == (100, 80)
    assert images["images/train/empty.png"].label_status == "Empty"
    assert images["images/train/missing.png"].label_status == "Missing"
    assert (
        len(catalog.issues) == 1
        and "not inferred negative" in catalog.issues[0].message
    )
    assert catalog.boxes[0].image_key == "images/train/scene.png"
    assert pixel_box(catalog.boxes[0], 100, 80).xyxy == pytest.approx((10, 20, 60, 50))
    assert all(path.read_bytes() == contents for path, contents in before.items())
    assert {path for path in tmp_path.rglob("*") if path.is_file()} == set(before)


def test_manifest_lists_aliases_duplicates_class_mapping_and_root_override(
    tmp_path: Path,
) -> None:
    root = tmp_path / "moved"
    manifest = dataset(root)
    (root / "subset.txt").write_text(
        "./images/train/scene.png\nimages/train/scene.png\n./images/train/lost.png\n"
    )
    manifest = tmp_path / "reference.yaml"
    manifest.write_text(
        "path: unavailable\ntrain: &files [subset.txt]\nval: *files\n"
        "names: {0: cat}\nnc: 1\n"
    )
    catalog = read_ultralytics(manifest, root_override=root)
    assert len(catalog.images) == 2 and len(catalog.boxes) == 1
    assert catalog.images[0].split == "train, train, val, val"
    assert any("Repeated" in issue.message for issue in catalog.issues)
    assert any("Image header" == issue.location for issue in catalog.issues)
    assert any(source.path == root / "subset.txt" for source in catalog.sources)
    assert catalog.classes[0].id == 0 and catalog.classes[0].name == "cat"
    assert "Dataset root" in catalog.description and str(root) in catalog.description


@pytest.mark.parametrize(
    "document",
    [
        "path: .\npath: other\n",
        "names: {0: a, '0': b}\ntrain: images\n",
        "names: {1: cat}\ntrain: images\n",
        "names: [cat]\nnc: 2\ntrain: images\n",
        "names: [cat]\ntrain: 42\n",
        "!!python/object/apply:os.system ['touch forbidden']",
    ],
)
def test_manifest_duplicate_unsafe_and_inconsistent_fields_are_diagnostic(
    tmp_path: Path, document: str
) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text(document)
    if "train: 42" in document:
        catalog = read_ultralytics(path)
        assert not catalog.images and catalog.issues
    else:
        with pytest.raises(ValueError):
            read_ultralytics(path)
    assert not (tmp_path / "forbidden").exists()


def test_manifest_download_is_data_missing_split_does_not_discard_valid_split(
    tmp_path: Path,
) -> None:
    manifest = dataset(tmp_path)
    manifest.write_text(
        "path: .\ntrain: missing\nval: images/train\nnames: [cat]\n"
        "download: 'touch forbidden'\n"
    )
    catalog = read_ultralytics(manifest)
    assert len(catalog.images) == 3 and len(catalog.boxes) == 1
    assert {issue.location for issue in catalog.issues} >= {
        "download",
        "train",
        "Label file",
    }
    assert not (tmp_path / "forbidden").exists()
    assert (
        label_path(tmp_path / "images/a/images/b/scene.jpg")
        == tmp_path / "images/a/labels/b/scene.txt"
    )


def test_manifest_declared_count_avoids_allocating_unused_class_names(
    tmp_path: Path,
) -> None:
    manifest = dataset(tmp_path)
    manifest.write_text("path: .\ntrain: images/train\nnc: 2000000\n")
    catalog = read_ultralytics(manifest)
    assert catalog.class_count == 2_000_000 and len(catalog.classes) == 1
    assert catalog.classes[0].name == "Class 0"
    with pytest.raises(ValueError, match="Duplicate"):
        decode_manifest("a: &base {path: .}\n<<: *base\npath: other\n")


def test_manifest_shared_label_stem_requires_explicit_association(
    tmp_path: Path,
) -> None:
    manifest = dataset(tmp_path)
    Image.new("RGB", (100, 80)).save(tmp_path / "images/train/scene.jpg")
    catalog = read_ultralytics(manifest)
    matches = [
        image for image in catalog.images if Path(image.reference).stem == "scene"
    ]
    assert len(matches) == 2 and all(
        image.label_status == "Ambiguous" for image in matches
    )
    assert len(catalog.boxes) == 2 and all(
        "Ambiguous" in box.diagnostics[-1] for box in catalog.boxes
    )
    assert (
        len(
            [issue for issue in catalog.issues if issue.location == "Label association"]
        )
        == 2
    )


def test_changed_label_between_manifest_records_rejects_complete_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = dataset(tmp_path)
    label = tmp_path / "labels/train/empty.txt"

    def changed(asset: AssetIdentity) -> ImageMetadata:
        if asset.path.name == "scene.png":
            label.write_text("external edit")
        return file_metadata(asset)

    monkeypatch.setattr(
        "datelier.io.annotations.readers.ultralytics.file_metadata", changed
    )
    with pytest.raises(ValueError, match="changed during command"):
        read_ultralytics(manifest)
    assert label.read_text() == "external edit"
