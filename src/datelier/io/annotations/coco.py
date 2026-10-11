"""COCO detection dataset JSON with exact image/category ID joins and raw xywh."""

from pathlib import Path

from datelier.inspection.annotations.types import (
    AnnotationCatalog,
    AnnotationClass,
    AnnotationFormat,
    AnnotationImage,
    AnnotationIssue,
    BoxCoordinates,
    BoxRecord,
)
from datelier.io.annotations.source import annotation_source
from datelier.io.annotations.values import integer, mapping, number, sequence, text
from datelier.io.tabular import decode_json


def read_coco(path: Path) -> AnnotationCatalog:
    with annotation_source(path) as (asset, stream):
        root = mapping(decode_json(stream.read().decode("utf-8-sig")), "COCO dataset")
        images: dict[int, AnnotationImage] = {}
        classes: dict[int, AnnotationClass] = {}
        for raw in sequence(root.get("images"), "COCO images"):
            value = mapping(raw, "COCO image")
            image_id = integer(value.get("id"), "Image id")
            if image_id in images:
                raise ValueError(
                    f"Duplicate COCO image id {image_id}; association is ambiguous"
                )
            width, height = (
                integer(value.get("width"), "Image width", positive=True),
                integer(value.get("height"), "Image height", positive=True),
            )
            images[image_id] = AnnotationImage(
                str(image_id),
                text(value.get("file_name"), "Image file_name"),
                (width, height),
                label_path=asset.path,
            )
        for raw in sequence(root.get("categories"), "COCO categories"):
            value = mapping(raw, "COCO category")
            class_id = integer(value.get("id"), "Category id")
            if class_id in classes:
                raise ValueError(f"Duplicate COCO category id {class_id}")
            classes[class_id] = AnnotationClass(
                class_id, text(value.get("name"), "Category name")
            )
        boxes: list[BoxRecord] = []
        issues: list[AnnotationIssue] = []
        ids: set[int] = set()
        for ordinal, raw in enumerate(
            sequence(root.get("annotations"), "COCO annotations")
        ):
            location = f"annotations[{ordinal}]"
            key: str | None = None
            try:
                value = mapping(raw, location)
                annotation_id = integer(value.get("id"), "Annotation id")
                if annotation_id in ids:
                    raise ValueError(f"Duplicate COCO annotation id {annotation_id}")
                ids.add(annotation_id)
                image_id = integer(value.get("image_id"), "Annotation image_id")
                key = str(image_id)
                if image_id not in images:
                    raise ValueError(
                        f"Unknown COCO image_id {image_id}; no image was reassigned"
                    )
                class_id = integer(value.get("category_id"), "Annotation category_id")
                bounds = sequence(value.get("bbox"), "Annotation bbox")
                if len(bounds) != 4:
                    raise ValueError("COCO detection bbox requires x,y,width,height")
                a, b, c, d = (number(item, "Box coordinate") for item in bounds)
                score = (
                    number(value["score"], "Annotation score")
                    if "score" in value
                    else None
                )
                diagnostics = (
                    ()
                    if class_id in classes
                    else (f"Unknown COCO category_id {class_id}; original ID retained",)
                )
                crowd = integer(value.get("iscrowd", 0), "iscrowd")
                if crowd not in (0, 1):
                    raise ValueError("COCO iscrowd requires 0 or 1")
                boxes.append(
                    BoxRecord(
                        asset,
                        ordinal,
                        key,
                        str(annotation_id),
                        class_id,
                        classes[class_id].name
                        if class_id in classes
                        else str(class_id),
                        (a, b, c, d),
                        BoxCoordinates.COCO,
                        score,
                        ("crowd",) if crowd else (),
                        location,
                        diagnostics,
                    )
                )
            except ValueError as error:
                issues.append(
                    AnnotationIssue(asset.path, location, str(error), key, repr(raw))
                )
    return AnnotationCatalog(
        AnnotationFormat.COCO,
        (asset,),
        tuple(images.values()),
        tuple(boxes),
        tuple(classes.values()),
        tuple(issues),
        "0-based top-left xywh; original image/category IDs; original source grid",
    )
