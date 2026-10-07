"""VOC XML preserves names, flags, original boxes and selectable index convention."""

from pathlib import Path
from xml.etree import ElementTree as ET

from datelier.inspection.annotations.types import (
    AnnotationCatalog,
    AnnotationClass,
    AnnotationFormat,
    AnnotationImage,
    AnnotationIssue,
    BoxCoordinates,
    BoxRecord,
)
from datelier.io.annotations.source import annotation_source, coordinates, finite_number
from datelier.io.xml_records import validate_xml_source


def _text(node: ET.Element, name: str) -> str:
    children = node.findall(name)
    if len(children) != 1 or not children[0].text or not children[0].text.strip():
        raise ValueError(f"VOC requires one nonempty {name} field")
    return children[0].text.strip()


def _optional_element(node: ET.Element, name: str) -> ET.Element | None:
    children = node.findall(name)
    if len(children) > 1:
        raise ValueError(f"VOC requires at most one {name} element")
    return children[0] if children else None


def _flags(node: ET.Element) -> tuple[str, ...]:
    result: list[str] = []
    for name in ("difficult", "truncated", "occluded"):
        if _optional_element(node, name) is not None:
            value = _text(node, name)
            if value not in ("0", "1"):
                raise ValueError(f"VOC {name} flag must be 0 or 1")
            if value == "1":
                result.append(name)
    return tuple(result)


def read_voc(
    path: Path, convention: BoxCoordinates = BoxCoordinates.VOC
) -> AnnotationCatalog:
    if convention not in (BoxCoordinates.VOC, BoxCoordinates.EDGES):
        raise ValueError("VOC boxes need an explicit xyxy index convention")
    with annotation_source(path) as (asset, stream):
        validate_xml_source(stream)
        try:
            root = ET.parse(stream).getroot()
        except ET.ParseError as error:
            raise ValueError(f"Malformed VOC XML: {error}") from error
        if root.tag != "annotation":
            raise ValueError("VOC XML root must be annotation")
        reference = _text(root, "filename")
        image_key = reference
        size = _optional_element(root, "size")
        dimensions = None
        if size is not None:
            width, height = int(_text(size, "width")), int(_text(size, "height"))
            if min(width, height) < 1:
                raise ValueError("VOC dimensions must be positive")
            dimensions = width, height
        boxes: list[BoxRecord] = []
        issues: list[AnnotationIssue] = []
        classes: dict[str, AnnotationClass] = {}
        for ordinal, node in enumerate(root.findall("object")):
            location = f"object {ordinal + 1}"
            try:
                name = _text(node, "name")
                bounds = _optional_element(node, "bndbox")
                if bounds is None:
                    raise ValueError("VOC object has no bndbox")
                original = coordinates(
                    [_text(bounds, name) for name in ("xmin", "ymin", "xmax", "ymax")]
                )
                flags = _flags(node)
                score_text = (
                    _text(node, "score")
                    if _optional_element(node, "score") is not None
                    else None
                )
                score = finite_number(score_text) if score_text is not None else None
                diagnostics = (
                    ("Optional score is a VOC XML extension",)
                    if score is not None
                    else ()
                )
                boxes.append(
                    BoxRecord(
                        asset,
                        ordinal,
                        image_key,
                        str(ordinal),
                        name,
                        name,
                        original,
                        convention,
                        score,
                        flags,
                        location,
                        diagnostics,
                    )
                )
                classes.setdefault(name, AnnotationClass(name, name))
            except ValueError as error:
                issues.append(
                    AnnotationIssue(
                        asset.path,
                        location,
                        str(error),
                        image_key,
                        ET.tostring(node, encoding="unicode"),
                    )
                )
    return AnnotationCatalog(
        AnnotationFormat.VOC,
        (asset,),
        (AnnotationImage(image_key, reference, dimensions, label_path=asset.path),),
        tuple(boxes),
        tuple(classes.values()),
        tuple(issues),
        convention.value,
    )
