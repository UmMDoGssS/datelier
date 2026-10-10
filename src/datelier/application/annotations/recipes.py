"""Small explicit recipe edits shared by native controls and behavioral tests."""

from dataclasses import replace

from datelier.inspection.annotations.settings import (
    AnnotationSource,
    ImageAssociationMapping,
)
from datelier.inspection.annotations.types import AnnotationClass


def class_names(text: str) -> tuple[AnnotationClass, ...]:
    classes: list[AnnotationClass] = []
    seen: set[int] = set()
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        fields = line.strip().split(maxsplit=1)
        if len(fields) != 2:
            raise ValueError(f"Line {number}: use a nonnegative class ID and name")
        try:
            index = int(fields[0])
        except ValueError as error:
            raise ValueError(f"Line {number}: class ID must be an integer") from error
        if index < 0 or index in seen:
            raise ValueError(
                f"Line {number}: class IDs must be distinct and nonnegative"
            )
        seen.add(index)
        classes.append(AnnotationClass(index, fields[1]))
    return tuple(classes)


def confirm_mapping(source: AnnotationSource, key: str, row: int) -> AnnotationSource:
    if not key or row < 0:
        raise ValueError("Choose a source image key and a nonnegative source row")
    mappings = tuple(item for item in source.mappings if item.image_key != key)
    return replace(source, mappings=(*mappings, ImageAssociationMapping(key, row)))
