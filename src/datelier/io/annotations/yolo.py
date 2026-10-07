"""YOLO normalized detection labels, with explicit optional confidence extension."""

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
from datelier.io.annotations.source import annotation_source, coordinates, finite_number


def read_yolo(
    path: Path,
    *,
    image_key: str | None = None,
    classes: tuple[AnnotationClass, ...] = (),
    scores: bool = False,
) -> AnnotationCatalog:
    names = {item.id: item.name for item in classes}
    if len(names) != len(classes) or any(
        not isinstance(item.id, int)
        or isinstance(item.id, bool)
        or item.id < 0
        or not item.name.strip()
        for item in classes
    ):
        raise ValueError("YOLO classes require unique nonnegative integer IDs")
    with annotation_source(path) as (asset, stream):
        key = image_key if image_key is not None else asset.path.stem
        if not key:
            raise ValueError("YOLO labels require an image association key")
        boxes: list[BoxRecord] = []
        issues: list[AnnotationIssue] = []
        for line, text in enumerate(stream.read().decode("utf-8-sig").splitlines(), 1):
            if not text.strip():
                continue
            location = f"line {line}"
            try:
                fields = text.split()
                if len(fields) != 5 and not (scores and len(fields) == 6):
                    raise ValueError(
                        "YOLO detection needs class and four normalized coordinates"
                        + (
                            " plus optional confidence"
                            if scores
                            else "; enable confidence explicitly for six-field rows"
                        )
                    )
                class_id = int(fields[0])
                if class_id < 0:
                    raise ValueError("YOLO class IDs start at zero")
                original = coordinates(fields[1:5])
                score = finite_number(fields[5]) if len(fields) == 6 else None
                diagnostics = (
                    (f"Class {class_id} has no name in the supplied mapping",)
                    if names and class_id not in names
                    else ()
                )
                if score is not None and not 0 <= score <= 1:
                    diagnostics += ("YOLO confidence lies outside 0–1",)
                boxes.append(
                    BoxRecord(
                        asset,
                        line - 1,
                        key,
                        str(line),
                        class_id,
                        names.get(class_id, str(class_id)),
                        original,
                        BoxCoordinates.YOLO,
                        score,
                        location=location,
                        diagnostics=diagnostics,
                    )
                )
            except ValueError as error:
                issues.append(
                    AnnotationIssue(asset.path, location, str(error), key, text)
                )
    return AnnotationCatalog(
        AnnotationFormat.YOLO,
        (asset,),
        (AnnotationImage(key, key, label_path=asset.path),),
        tuple(boxes),
        classes,
        tuple(issues),
        "Normalized centre/size; zero-based classes; original source grid"
        + ("; optional trailing confidence enabled" if scores else ""),
    )
