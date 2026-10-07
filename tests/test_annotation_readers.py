"""Equivalent original-coordinate boxes, provenance and malformed label outcomes."""

from dataclasses import replace
from pathlib import Path

import pytest

from datelier.inspection.annotations.geometry import oriented_box, pixel_box
from datelier.inspection.annotations.types import (
    AnnotationClass,
    BoxCoordinates,
    BoxRecord,
)
from datelier.inspection.references.types import AssetIdentity
from datelier.io.annotations.source import annotation_source
from datelier.io.annotations.voc import read_voc
from datelier.io.annotations.yolo import read_yolo


def voc(objects: str, *, header: str = "") -> str:
    return f"""<annotation><filename>scene.png</filename>
    <size><width>100</width><height>80</height></size>{header}{objects}</annotation>"""


def object_xml(bounds: str = "11 21 60 50", *, extra: str = "") -> str:
    fields = "".join(
        f"<{name}>{value}</{name}>"
        for name, value in zip(
            ("xmin", "ymin", "xmax", "ymax"), bounds.split(), strict=True
        )
    )
    return f"<object><name>cat</name><bndbox>{fields}</bndbox>{extra}</object>"


def record(
    tmp_path: Path,
    convention: BoxCoordinates,
    original: tuple[float, float, float, float],
) -> BoxRecord:
    return BoxRecord(
        AssetIdentity(tmp_path / "labels", 0, 0),
        0,
        "scene",
        "one",
        0,
        "cat",
        original,
        convention,
    )


def test_voc_and_yolo_equivalent_boxes_retain_original_class_and_flags(
    tmp_path: Path,
) -> None:
    xml, text = tmp_path / "scene.xml", tmp_path / "scene.txt"
    xml.write_text(
        voc(
            object_xml(
                extra="<difficult>1</difficult><truncated>0</truncated><score>0.8</score>"
            )
        )
    )
    text.write_text("0 0.35 0.4375 0.5 0.375 0.8\n")
    originals = xml.read_bytes(), text.read_bytes()
    a = read_voc(xml)
    b = read_yolo(
        text, image_key="scene.png", classes=(AnnotationClass(0, "cat"),), scores=True
    )
    assert a.images[0].dimensions == (100, 80) and b.images[0].dimensions is None
    first, second = a.boxes[0], b.boxes[0]
    assert first.original == (11, 21, 60, 50) and second.original == (
        0.35,
        0.4375,
        0.5,
        0.375,
    )
    assert (
        first.class_id == "cat"
        and second.class_id == 0
        and first.class_name == second.class_name == "cat"
    )
    assert first.score == second.score == 0.8 and first.flags == ("difficult",)
    assert first.asset.path == xml and second.location == "line 1"
    assert first.diagnostics and not a.issues and not b.issues
    assert pixel_box(first, 100, 80).xyxy == pytest.approx((10, 20, 60, 50))
    assert pixel_box(second, 100, 80).xyxy == pytest.approx((10, 20, 60, 50))
    assert (xml.read_bytes(), text.read_bytes()) == originals


def test_voc_index_choice_one_pixel_and_float_boxes_are_explicit(
    tmp_path: Path,
) -> None:
    path = tmp_path / "one.xml"
    path.write_text(voc(object_xml("1 1 1 1") + object_xml("2.5 3.5 8.5 9.5")))
    catalog = read_voc(path)
    one = pixel_box(catalog.boxes[0], 100, 80)
    assert one.xyxy == (0, 0, 1, 1) and one.width == one.height == 1
    assert pixel_box(catalog.boxes[1], 100, 80).xyxy == (1.5, 2.5, 8.5, 9.5)
    edges = read_voc(path, BoxCoordinates.EDGES)
    assert edges.boxes[1].original == catalog.boxes[1].original
    assert pixel_box(edges.boxes[1], 100, 80).xyxy == (2.5, 3.5, 8.5, 9.5)
    with pytest.raises(ValueError, match="positive"):
        pixel_box(edges.boxes[0], 100, 80)
    with pytest.raises(ValueError, match="xyxy"):
        read_voc(path, BoxCoordinates.YOLO)


def test_voc_invalid_objects_retain_source_location_and_original_xml(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.xml"
    path.write_text(
        voc(
            object_xml()
            + "<object><name>bad</name></object>"
            + object_xml("nan 0 5 5")
            + object_xml(extra="<truncated>2</truncated>")
            + object_xml(extra="<bndbox/>")
        )
    )
    catalog = read_voc(path)
    assert len(catalog.boxes) == 1 and len(catalog.issues) == 4
    assert [issue.location for issue in catalog.issues] == [
        f"object {n}" for n in range(2, 6)
    ]
    assert all(
        issue.image_key == "scene.png" and "<object>" in issue.original
        for issue in catalog.issues
    )
    assert "finite" in catalog.issues[1].message
    assert (
        "flag" in catalog.issues[2].message
        and "at most one" in catalog.issues[3].message
    )


@pytest.mark.parametrize(
    "text",
    [
        "<annotation>",
        "<wrong/>",
        "<!DOCTYPE x [<!ENTITY y 'value'>]><annotation/>",
        "<annotation><filename>a</filename><filename>b</filename></annotation>",
    ],
)
def test_malformed_or_ambiguous_voc_fails_without_partial_catalog(
    tmp_path: Path, text: str
) -> None:
    path = tmp_path / "bad.xml"
    path.write_text(text)
    with pytest.raises(ValueError):
        read_voc(path)


def test_yolo_original_line_indices_empty_labels_and_class_diagnostics(
    tmp_path: Path,
) -> None:
    path = tmp_path / "labels.txt"
    path.write_text(
        "\n0 0.5 0.5 1 1\n\n2 0.5 0.5 0.2 0.2\n-1 0 0 1 1\n"
        "0 0.5 0.5 0.2 0.2 0.9\n0 0 0 nan 1\n0 0 0 1 1 0 0\n"
    )
    catalog = read_yolo(path, classes=(AnnotationClass(0, "cat"),))
    assert [box.ordinal for box in catalog.boxes] == [1, 3]
    assert [box.location for box in catalog.boxes] == ["line 2", "line 4"]
    assert (
        catalog.boxes[1].class_id == 2 and "mapping" in catalog.boxes[1].diagnostics[0]
    )
    assert len(catalog.issues) == 4 and catalog.issues[1].location == "line 6"
    assert "confidence" in catalog.issues[1].message
    assert pixel_box(catalog.boxes[0], 100, 80).xyxy == (0, 0, 100, 80)
    path.write_text("")
    empty = read_yolo(path)
    assert not empty.boxes and not empty.issues and len(empty.images) == 1
    with pytest.raises(ValueError, match="unique"):
        read_yolo(path, classes=(AnnotationClass(0, "a"), AnnotationClass(0, "b")))


@pytest.mark.parametrize(
    "convention,values",
    [
        (BoxCoordinates.VOC, (2.5, 2, 2, 3)),
        (BoxCoordinates.EDGES, (2, 3, 2, 4)),
        (BoxCoordinates.COCO, (0, 0, -1, 2)),
        (BoxCoordinates.YOLO, (0.5, 0.5, 0, 1)),
    ],
)
def test_invalid_boxes_are_rejected_without_clamping(
    tmp_path: Path,
    convention: BoxCoordinates,
    values: tuple[float, float, float, float],
) -> None:
    original = record(tmp_path, convention, values)
    with pytest.raises(ValueError):
        pixel_box(original, 100, 80)
    assert original.original == values


def test_out_of_bounds_and_normalized_diagnostics_preserve_coordinates(
    tmp_path: Path,
) -> None:
    original = record(tmp_path, BoxCoordinates.YOLO, (-0.1, 0.5, 0.4, 1.2))
    converted = pixel_box(original, 100, 80)
    assert converted.xyxy == pytest.approx((-30, -8, 10, 88))
    assert len(converted.diagnostics) == 2 and converted.record is original
    with pytest.raises(ValueError, match="finite"):
        pixel_box(replace(original, original=(0, 0, float("inf"), 1)), 100, 80)


@pytest.mark.parametrize(
    "orientation,expected",
    [
        (1, (10, 20, 60, 50)),
        (2, (40, 20, 90, 50)),
        (3, (40, 30, 90, 60)),
        (4, (10, 30, 60, 60)),
        (5, (20, 10, 50, 60)),
        (6, (30, 10, 60, 60)),
        (7, (30, 40, 60, 90)),
        (8, (20, 40, 50, 90)),
    ],
)
def test_all_exif_box_edges_keep_geometry(
    tmp_path: Path, orientation: int, expected: tuple[int, int, int, int]
) -> None:
    original = record(tmp_path, BoxCoordinates.EDGES, (10, 20, 60, 50))
    converted = pixel_box(original, 100, 80)
    assert oriented_box(converted, 100, 80, orientation) == expected
    assert converted.xyxy == (10, 20, 60, 50)


def test_changed_annotation_snapshot_is_rejected_and_no_source_is_written(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source.txt"
    path.write_text("original")
    with pytest.raises(ValueError, match="changed"):
        with annotation_source(path) as (asset, stream):
            assert stream.read() == b"original" and asset.size == 8
            path.write_text("external edit")
    assert path.read_text() == "external edit"
