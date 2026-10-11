"""Explicit annotation preparation against scoped current records; no pixel decoding."""

from concurrent.futures import CancelledError
from dataclasses import replace
from threading import Event

from datelier.core import Dataset
from datelier.inspection.annotations.association.matching import (
    source_key,
    target_index,
)
from datelier.inspection.annotations.association.types import (
    AssociatedBox,
    AssociatedImage,
    AssociatedSource,
)
from datelier.inspection.annotations.geometry import oriented_box, pixel_box
from datelier.inspection.annotations.settings import (
    AnnotationSource,
)
from datelier.inspection.annotations.types import (
    AnnotationCatalog,
    AnnotationIssue,
    BoxRecord,
)
from datelier.inspection.arrays import ArrayCatalog, ArrayRecordMapping
from datelier.inspection.images.decoding.sources import image_metadata, locate_image
from datelier.inspection.images.profiles import ImageProgress
from datelier.inspection.images.types import ImageLocator, ImageMetadata
from datelier.inspection.references import ReferenceSettings
from datelier.inspection.references.index import ReferenceIndex
from datelier.io.annotations.source import verify_sources


def check_cancelled(stop: Event) -> None:
    if stop.is_set():
        raise CancelledError("Annotation association abandoned")


def verify_associated_source(source: AssociatedSource) -> None:
    if source.catalog is not None:
        verify_sources(
            (
                *source.catalog.sources,
                *(
                    image.locator.asset
                    for image in source.images
                    if image.locator is not None and image.locator.asset is not None
                ),
            )
        )


def associate_source(
    dataset: Dataset,
    file_id: str,
    view_name: str,
    column: str,
    source: AnnotationSource,
    annotations: AnnotationCatalog,
    references: ReferenceSettings,
    index: ReferenceIndex | None,
    stop: Event,
    progress: ImageProgress,
    metadata_cache: dict[int, tuple[ImageLocator, ImageMetadata]],
    catalog: ArrayCatalog | None = None,
    mapping: ArrayRecordMapping | None = None,
) -> AssociatedSource:
    targets = target_index(
        dataset,
        source,
        column,
        file_id,
        view_name,
        references,
        index,
        catalog,
        mapping,
        stop,
    )
    explicit = {item.image_key: item for item in source.mappings}
    confirmed = dict(explicit)
    grouped: dict[str, list[BoxRecord]] = {}
    for box in annotations.boxes:
        grouped.setdefault(box.image_key, []).append(box)
    images: list[AssociatedImage] = []
    boxes: list[AssociatedBox] = []
    issues = list(annotations.issues)
    for number, image in enumerate(annotations.images):
        check_cancelled(stop)
        progress.update(
            f"Associating {source.name or source.id}", number, len(annotations.images)
        )
        manual = explicit.get(image.key)
        if manual is not None:
            candidates = (manual.row_id,) if manual.row_id in targets.positions else ()
            if not candidates:
                images.append(
                    AssociatedImage(
                        image,
                        "Mapped row unavailable",
                        diagnostics=(
                            "The mapped source row is excluded or absent; "
                            "no replacement was chosen",
                        ),
                    )
                )
                continue
            key = targets.pins.get(manual.row_id)
            if manual.expected_key is not None and manual.expected_key != key:
                images.append(
                    AssociatedImage(
                        image,
                        "Mapped key changed",
                        candidates,
                        diagnostics=(
                            "Mapped row now has another image/key; "
                            "confirm the association again",
                        ),
                    )
                )
                continue
            confirmed[image.key] = replace(manual, expected_key=key)
        elif image.label_status == "Ambiguous":
            images.append(
                AssociatedImage(
                    image,
                    "Ambiguous",
                    diagnostics=(
                        "Manifest label matches several images; "
                        "explicit source-row mapping required",
                    ),
                )
            )
            continue
        else:
            try:
                candidates = targets.candidates.get(source_key(source, image), ())
            except ValueError as error:
                images.append(
                    AssociatedImage(image, "No match", diagnostics=(str(error),))
                )
                continue
        if len(candidates) != 1:
            images.append(
                AssociatedImage(
                    image,
                    "Ambiguous" if candidates else "No match",
                    candidates,
                    diagnostics=(
                        "Choose an explicit source-row mapping"
                        if candidates
                        else "No current image/key matches this source image",
                    ),
                )
            )
            continue
        row_id = candidates[0]
        try:
            if row_id not in metadata_cache:
                locator = locate_image(
                    dataset,
                    file_id,
                    view_name,
                    column,
                    targets.positions[row_id],
                    references,
                    index,
                    catalog,
                    mapping,
                )
                metadata_cache[row_id] = locator, image_metadata(locator)
            locator, metadata = metadata_cache[row_id]
        except Exception as error:
            images.append(
                AssociatedImage(
                    image, "Image error", candidates, diagnostics=(str(error),)
                )
            )
            continue
        dimensions = metadata.source_width, metadata.source_height
        diagnostics = (
            ()
            if image.dimensions is None or image.dimensions == dimensions
            else (
                f"Declared dimensions {image.dimensions} differ from original "
                f"image {dimensions}; original coordinates retained",
            )
        )
        images.append(
            AssociatedImage(
                image, "Ready", candidates, locator, dimensions, diagnostics
            )
        )
        for raw in grouped.get(image.key, ()):
            check_cancelled(stop)
            try:
                converted = pixel_box(raw, *dimensions)
                converted = replace(
                    converted, diagnostics=(*converted.diagnostics, *diagnostics)
                )
                boxes.append(
                    AssociatedBox(
                        source.id,
                        locator.origin,
                        converted,
                        oriented_box(converted, *dimensions, metadata.orientation),
                    )
                )
            except ValueError as error:
                issues.append(
                    AnnotationIssue(
                        raw.asset.path,
                        raw.location,
                        str(error),
                        image.key,
                        repr(raw.original),
                    )
                )
    check_cancelled(stop)
    known = {image.key for image in annotations.images}
    for manual in source.mappings:
        if manual.image_key not in known:
            issues.append(
                AnnotationIssue(
                    annotations.sources[0].path
                    if annotations.sources
                    else dataset.source.path,
                    "Mapping",
                    "Source image key is absent from this annotation scope",
                    manual.image_key,
                )
            )
    recipe = replace(source, mappings=tuple(confirmed.values()))
    result = AssociatedSource(
        recipe, annotations, tuple(images), tuple(boxes), tuple(issues)
    )
    verify_associated_source(result)
    return result
