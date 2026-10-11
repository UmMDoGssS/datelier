"""First-pass source-aligned metadata and moments, without retained decoded grids."""

from dataclasses import dataclass
from threading import Event

import polars as pl

from datelier.core.dataset import Dataset
from datelier.inspection.arrays.mapping import ArrayLayout, ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.images.decoding import ImageStore
from datelier.inspection.images.decoding.pixels import check_cancelled
from datelier.inspection.images.decoding.sources import (
    ImageReferenceError,
    image_metadata,
    locate_image,
)
from datelier.inspection.images.profiles.moments import ChannelMoments
from datelier.inspection.images.profiles.records import (
    CHANNEL_SCHEMA,
    RECORD_SCHEMA,
    ProfileRecord,
    profile_record,
    record_row,
)
from datelier.inspection.images.profiles.types import (
    ChannelKey,
    ImageProfileSettings,
    ImageProgress,
)
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays import ArrayStore


@dataclass(frozen=True)
class ImageProfileScan:
    dataset: Dataset
    file_id: str
    view_name: str
    settings: ImageProfileSettings
    mapping: ArrayRecordMapping | None
    records: pl.DataFrame
    channel_records: pl.DataFrame
    successful: tuple[ProfileRecord, ...]
    pooled: dict[ChannelKey, ChannelMoments]
    total_pixels: int
    profiled_pixels: int


def validate_profile_input(
    dataset: Dataset,
    settings: ImageProfileSettings,
    catalog: ArrayCatalog | None,
    mapping: ArrayRecordMapping | None,
) -> None:
    settings.validate()
    if settings.column is None:
        raise ValueError("Choose an image field or confirmed image mapping")
    if mapping is not None:
        if settings.column != mapping.member:
            raise ValueError("Choose the current confirmed image member")
        if catalog is None or mapping.layout != ArrayLayout.IMAGE:
            raise ValueError("Collection colors require a confirmed image mapping")
        mapping.record_count(catalog)
    elif dataset.table.schema.get(settings.column) != pl.String:
        raise ValueError("Image references require a physical String field")


def scan_image_profile(
    dataset: Dataset,
    file_id: str,
    view_name: str,
    settings: ImageProfileSettings,
    positions: pl.Series,
    references: ReferenceSettings,
    index: ReferenceIndex | None,
    images: ImageStore,
    arrays: ArrayStore,
    stop: Event,
    progress: ImageProgress,
    catalog: ArrayCatalog | None = None,
    mapping: ArrayRecordMapping | None = None,
) -> ImageProfileScan:
    validate_profile_input(dataset, settings, catalog, mapping)
    assert settings.column is not None
    row_ids = dataset.row_ids
    references_column = dataset.table[settings.column] if mapping is None else None
    records: list[tuple[object, ...]] = []
    channel_records: list[tuple[object, ...]] = []
    successful: list[ProfileRecord] = []
    pooled: dict[ChannelKey, ChannelMoments] = {}
    total_pixels = profiled_pixels = 0
    for number, position in enumerate(positions):
        check_cancelled(stop)
        row_id = int(row_ids[position])
        reference = (
            str(references_column[position])
            if references_column is not None and references_column[position] is not None
            else None
        )
        progress.update(
            "Image dimensions and channel statistics", number, len(positions)
        )
        if references_column is not None and references_column[position] is None:
            records.append(
                record_row(
                    row_id,
                    int(position),
                    reference,
                    "Null",
                    "Image reference is null",
                )
            )
            continue
        try:
            locator = locate_image(
                dataset,
                file_id,
                view_name,
                settings.column,
                int(position),
                references,
                index,
                catalog,
                mapping,
            )
            metadata = image_metadata(locator)
            record = profile_record(locator, metadata, settings, images, arrays, stop)
            check_cancelled(stop)
            # Merge only after the source lease verifies this record.
            for name, moments in zip(metadata.channels, record.moments, strict=True):
                key = ChannelKey(metadata.mode, name, metadata.dtype.str)
                pooled.setdefault(key, ChannelMoments()).merge(moments)
                summary = moments.summary(key)
                channel_records.append(
                    (
                        row_id,
                        metadata.mode,
                        name,
                        metadata.dtype.str,
                        summary.values,
                        summary.finite,
                        summary.nonfinite,
                        str(summary.minimum) if summary.minimum is not None else None,
                        str(summary.maximum) if summary.maximum is not None else None,
                        summary.mean,
                        summary.stddev,
                    )
                )
            records.append(
                record_row(row_id, int(position), reference, "Ready", record=record)
            )
            successful.append(record)
            total_pixels += metadata.width * metadata.height
            profiled_pixels += record.profiled_pixels
        except (ImageReferenceError, FileNotFoundError) as error:
            records.append(
                record_row(row_id, int(position), reference, "Unresolved", str(error))
            )
        except Exception as error:
            check_cancelled(stop)
            records.append(
                record_row(row_id, int(position), reference, "Failed", str(error))
            )
    check_cancelled(stop)
    return ImageProfileScan(
        dataset,
        file_id,
        view_name,
        settings,
        mapping,
        pl.DataFrame(records, schema=RECORD_SCHEMA, orient="row"),
        pl.DataFrame(channel_records, schema=CHANNEL_SCHEMA, orient="row"),
        tuple(successful),
        pooled,
        total_pixels,
        profiled_pixels,
    )
