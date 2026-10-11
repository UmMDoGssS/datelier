"""Explicit worker statistics over associated original geometry; no file reads."""

from collections import Counter
from threading import Event

import numpy as np
import polars as pl

from datelier.inspection.annotations.association import (
    AssociatedSource,
    PreparedAnnotations,
)
from datelier.inspection.annotations.association.associate import check_cancelled
from datelier.inspection.annotations.profiles.types import (
    AnnotationProfile,
    AnnotationProfiles,
    ClassCount,
)
from datelier.inspection.images.profiles import ChannelKey, ImageProgress
from datelier.inspection.images.profiles.moments import (
    ChannelMoments,
    histogram,
    normalized_values,
)

FIELDS = ("Width", "Height", "Area", "Aspect ratio")
BOX_SCHEMA = {
    "box_index": pl.UInt64,
    "row_id": pl.UInt64,
    "image_key": pl.String,
    "class_id": pl.String,
    "class_name": pl.String,
    "score": pl.Float64,
    "width": pl.Float64,
    "height": pl.Float64,
    "area": pl.Float64,
    "aspect_ratio": pl.Float64,
    "diagnostic": pl.String,
}


def source_profile(
    source: AssociatedSource, bins: int, stop: Event
) -> AnnotationProfile:
    classes: Counter[tuple[int | str, str]] = Counter()
    class_rows: dict[tuple[int | str, str], set[int]] = {}
    rows: list[tuple[object, ...]] = []
    for number, box in enumerate(source.boxes):
        if number % 512 == 0 and stop.wait(0.001):
            check_cancelled(stop)
        record = box.box.record
        classes[record.class_id, record.class_name] += 1
        class_rows.setdefault((record.class_id, record.class_name), set()).add(
            box.origin.row_id
        )
        x1, y1, x2, y2 = map(np.longdouble, box.box.xyxy)
        width, height = x2 - x1, y2 - y1
        rows.append(
            (
                number,
                box.origin.row_id,
                record.image_key,
                str(record.class_id),
                record.class_name,
                record.score,
                float(width),
                float(height),
                float(width * height),
                float(width / height),
                "; ".join(box.box.diagnostics),
            )
        )
    records = pl.DataFrame(rows, schema=BOX_SCHEMA, orient="row")
    summaries = []
    distributions = []
    for label, field in zip(
        FIELDS, ("width", "height", "area", "aspect_ratio"), strict=True
    ):
        check_cancelled(stop)
        values = records[field].to_numpy()
        accumulator = ChannelMoments()
        accumulator.add(values)
        summary = accumulator.summary(ChannelKey("Boxes", label, "float64"))
        counts = np.zeros(bins, dtype=np.float64)
        if (
            summary.finite
            and summary.minimum is not None
            and summary.maximum is not None
        ):
            normalized = normalized_values(values, summary.minimum, summary.maximum)
            counts[:] = np.histogram(
                np.asarray(normalized, dtype=np.float64),
                bins=np.linspace(0, 1, bins + 1),
            )[0]
        summaries.append(summary)
        distributions.append(histogram(label, counts, summary.minimum, summary.maximum))
    outcomes = Counter(item.status for item in source.images)
    raw_by_image = (
        Counter(box.image_key for box in source.catalog.boxes)
        if source.catalog
        else Counter()
    )
    quality = (
        ("Image keys", len(source.images)),
        ("Associated image keys", outcomes["Ready"]),
        ("Ambiguous image keys", outcomes["Ambiguous"]),
        ("Unmatched image keys", outcomes["No match"]),
        (
            "Unavailable or changed mappings",
            outcomes["Mapped row unavailable"] + outcomes["Mapped key changed"],
        ),
        ("Image errors", outcomes["Image error"]),
        (
            "Missing labels",
            sum(item.image.label_status == "Missing" for item in source.images),
        ),
        (
            "Invalid / unreadable labels",
            sum(
                item.image.label_status in ("Invalid", "Unreadable")
                for item in source.images
            ),
        ),
        (
            "Present labels without boxes",
            sum(
                item.image.label_status == "Present"
                and not raw_by_image[item.image.key]
                for item in source.images
            ),
        ),
        ("Original parsed boxes", len(source.catalog.boxes) if source.catalog else 0),
        ("Usable associated boxes", len(source.boxes)),
        ("Boxes with warnings", sum(bool(box.box.diagnostics) for box in source.boxes)),
        ("Issues", len(source.issues)),
        ("Source errors", int(bool(source.error))),
    )
    return AnnotationProfile(
        source.recipe.id,
        tuple(
            ClassCount(key[0], key[1], count, tuple(sorted(class_rows[key])))
            for key, count in sorted(
                classes.items(), key=lambda item: (-item[1], str(item[0]))
            )
        ),
        quality,
        records,
        tuple(summaries),
        tuple(distributions),
    )


def prepare_profiles(
    annotations: PreparedAnnotations, bins: int, stop: Event, progress: ImageProgress
) -> AnnotationProfiles:
    if not 1 <= bins <= 256:
        raise ValueError("Annotation profiles require 1–256 bins")
    sources = []
    for number, source in enumerate(annotations.sources):
        check_cancelled(stop)
        progress.update(
            "Profiling annotation sources", number, len(annotations.sources)
        )
        sources.append(source_profile(source, bins, stop))
    check_cancelled(stop)
    progress.update("Annotation profiles ready", len(sources), len(sources))
    return AnnotationProfiles(annotations, bins, tuple(sources))
