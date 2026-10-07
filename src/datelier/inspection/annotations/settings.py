"""Finite annotation source and explicit target-association recipes."""

from dataclasses import dataclass
from enum import StrEnum

from datelier.inspection.annotations.types import (
    AnnotationClass,
    AnnotationFormat,
    BoxCoordinates,
)


class ImageMatch(StrEnum):
    PATH = "Resolved image path"
    FILENAME = "Filename"
    STEM = "Filename stem"
    COLUMN = "Image key column"


@dataclass(frozen=True)
class ImageAssociationMapping:
    image_key: str
    row_id: int
    expected_key: str | None = None


@dataclass(frozen=True)
class AnnotationSource:
    id: str
    path: str
    format: AnnotationFormat = AnnotationFormat.VOC
    name: str = ""
    image_root: str | None = None
    dataset_root: str | None = None
    match: ImageMatch = ImageMatch.FILENAME
    key_column: str | None = None
    convention: BoxCoordinates = BoxCoordinates.VOC
    scores: bool = False
    classes: tuple[AnnotationClass, ...] = ()
    mappings: tuple[ImageAssociationMapping, ...] = ()

    def validate(self) -> None:
        if not self.id or not self.path.strip():
            raise ValueError("Annotation sources need an identity and local path")
        if self.format == AnnotationFormat.VOC and self.convention not in (
            BoxCoordinates.VOC,
            BoxCoordinates.EDGES,
        ):
            raise ValueError("VOC requires a selected xyxy index convention")
        if self.match == ImageMatch.COLUMN and not self.key_column:
            raise ValueError("Choose the table column containing annotation image keys")
        if len({item.image_key for item in self.mappings}) != len(self.mappings) or any(
            not item.image_key or item.row_id < 0 for item in self.mappings
        ):
            raise ValueError(
                "Choose one nonnegative source row per annotation image key"
            )


@dataclass(frozen=True)
class AnnotationSettings:
    column: str | None = None
    sources: tuple[AnnotationSource, ...] = ()

    def validate(self) -> None:
        if len({source.id for source in self.sources}) != len(self.sources):
            raise ValueError("Annotation source identities must be distinct")
        for source in self.sources:
            source.validate()
