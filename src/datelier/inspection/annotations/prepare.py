"""Explicit combined annotation commands, isolating unusable sources."""

from threading import Event

from datelier.core.dataset import Dataset
from datelier.inspection.annotations.associate import (
    associate_source,
    check_cancelled,
    verify_associated_source,
)
from datelier.inspection.annotations.association_types import (
    AssociatedSource,
    PreparedAnnotations,
)
from datelier.inspection.annotations.settings import AnnotationSettings
from datelier.inspection.arrays.mapping import ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.images.profile_types import ImageProgress
from datelier.inspection.images.types import ImageLocator, ImageMetadata
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.annotations.loading import load_annotations
from datelier.io.arrays.storage import ArrayStore


def prepare_annotations(
    dataset: Dataset,
    file_id: str,
    view_name: str,
    settings: AnnotationSettings,
    references: ReferenceSettings,
    index: ReferenceIndex | None,
    stop: Event,
    progress: ImageProgress,
    catalog: ArrayCatalog | None = None,
    mapping: ArrayRecordMapping | None = None,
) -> PreparedAnnotations:
    settings.validate()
    if settings.column is None:
        raise ValueError("Choose an image field or confirmed image mapping")
    sources: list[AssociatedSource] = []
    metadata: dict[int, tuple[ImageLocator, ImageMetadata]] = {}
    for source in settings.sources:
        check_cancelled(stop)
        progress.update(f"Reading {source.name or source.id}", 0, 1)
        try:
            annotations = load_annotations(source, stop)
            sources.append(
                associate_source(
                    dataset,
                    file_id,
                    view_name,
                    settings.column,
                    source,
                    annotations,
                    references,
                    index,
                    stop,
                    progress,
                    metadata,
                    catalog,
                    mapping,
                )
            )
        except Exception as error:
            check_cancelled(stop)
            sources.append(AssociatedSource(source, None, error=str(error)))
    check_cancelled(stop)
    if catalog is not None and mapping is not None:
        ArrayStore.check_source(catalog)
    for number, source in enumerate(sources):
        if not source.error:
            try:
                verify_associated_source(source)
            except (ValueError, OSError) as error:
                sources[number] = AssociatedSource(
                    source.recipe,
                    source.catalog,
                    issues=source.issues,
                    error=str(error),
                )
    progress.update("Annotations ready", len(sources), len(sources))
    return PreparedAnnotations(
        file_id, view_name, dataset.revision, settings.column, tuple(sources)
    )
