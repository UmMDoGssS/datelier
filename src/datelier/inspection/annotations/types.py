"""Immutable source records and explicit detection coordinate conventions."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from datelier.inspection.references.types import AssetIdentity


class AnnotationFormat(StrEnum):
    VOC = "Pascal VOC XML"
    YOLO = "YOLO detection text"
    COCO = "COCO JSON"
    ULTRALYTICS = "Ultralytics manifest"


class BoxCoordinates(StrEnum):
    VOC = "1-based inclusive xyxy"
    EDGES = "0-based pixel-edge xyxy"
    YOLO = "Normalized centre xywh"
    COCO = "0-based pixel xywh"


@dataclass(frozen=True)
class AnnotationClass:
    id: int | str
    name: str


@dataclass(frozen=True)
class AnnotationImage:
    key: str
    reference: str
    dimensions: tuple[int, int] | None = None
    split: str = ""
    label_path: Path | None = None
    label_status: str = "Present"


@dataclass(frozen=True)
class AnnotationIssue:
    path: Path
    location: str
    message: str
    image_key: str | None = None
    original: str = ""


@dataclass(frozen=True)
class BoxRecord:
    asset: AssetIdentity
    ordinal: int
    image_key: str
    annotation_id: str
    class_id: int | str
    class_name: str
    original: tuple[float, float, float, float]
    coordinates: BoxCoordinates
    score: float | None = None
    flags: tuple[str, ...] = ()
    location: str = ""
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnnotationCatalog:
    format: AnnotationFormat
    sources: tuple[AssetIdentity, ...]
    images: tuple[AnnotationImage, ...]
    boxes: tuple[BoxRecord, ...]
    classes: tuple[AnnotationClass, ...] = ()
    issues: tuple[AnnotationIssue, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class PixelBox:
    record: BoxRecord
    xyxy: tuple[float, float, float, float]
    diagnostics: tuple[str, ...] = ()

    @property
    def width(self) -> float:
        return self.xyxy[2] - self.xyxy[0]

    @property
    def height(self) -> float:
        return self.xyxy[3] - self.xyxy[1]
