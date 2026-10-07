"""File/view/source-row-qualified annotation preparation and association outcomes."""

from dataclasses import dataclass, field

from datelier.core.dataset import DatasetRevision
from datelier.inspection.annotations.settings import AnnotationSource
from datelier.inspection.annotations.types import (
    AnnotationCatalog,
    AnnotationImage,
    AnnotationIssue,
    PixelBox,
)
from datelier.inspection.images.types import ImageLocator, ImageOrigin


@dataclass(frozen=True)
class AssociatedBox:
    source_id: str
    origin: ImageOrigin
    box: PixelBox
    oriented: tuple[float, float, float, float]

    @property
    def identity(self) -> tuple[ImageOrigin, str, str, int, str]:
        record = self.box.record
        return (
            self.origin,
            self.source_id,
            str(record.asset.path),
            record.ordinal,
            record.image_key,
        )


@dataclass(frozen=True)
class AssociatedImage:
    image: AnnotationImage
    status: str
    candidates: tuple[int, ...] = ()
    locator: ImageLocator | None = None
    dimensions: tuple[int, int] | None = None
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssociatedSource:
    recipe: AnnotationSource
    catalog: AnnotationCatalog | None
    images: tuple[AssociatedImage, ...] = ()
    boxes: tuple[AssociatedBox, ...] = ()
    issues: tuple[AnnotationIssue, ...] = ()
    error: str = ""


@dataclass(frozen=True)
class PreparedAnnotations:
    file_id: str
    view_name: str
    revision: DatasetRevision
    column: str
    sources: tuple[AssociatedSource, ...]
    by_image: dict[ImageOrigin, tuple[AssociatedBox, ...]] = field(default_factory=dict)
