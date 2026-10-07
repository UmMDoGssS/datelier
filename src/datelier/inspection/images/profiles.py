"""Explicit image collection statistics, streamed in two source-checked passes."""

from contextlib import ExitStack
from threading import Event

import numpy as np
import polars as pl

from datelier.core.dataset import Dataset
from datelier.inspection.arrays.mapping import ArrayLayout, ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.images.moments import (
    ChannelMoments,
    histogram,
    normalized_values,
)
from datelier.inspection.images.pixels import (
    check_cancelled,
    original_pixels,
    pixel_batches,
)
from datelier.inspection.images.profile_records import (
    CHANNEL_SCHEMA,
    RECORD_SCHEMA,
    ProfileRecord,
    profile_record,
    record_row,
)
from datelier.inspection.images.profile_types import (
    ChannelKey,
    ChannelSummary,
    ImageHistogram,
    ImageProfile,
    ImageProfileSettings,
    ImageProgress,
    ImageScopeMode,
)
from datelier.inspection.images.sources import (
    ImageReferenceError,
    image_metadata,
    locate_image,
)
from datelier.inspection.images.storage import ImageStore
from datelier.inspection.records.prepare import prepare_records
from datelier.inspection.records.types import InspectSettings, RecordMode
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays.storage import ArrayStore


def image_positions(
    dataset: Dataset, settings: ImageProfileSettings, selection: tuple[int, ...]
) -> pl.Series:
    scope = settings.scope
    if scope.mode == ImageScopeMode.COLLECTION:
        return pl.int_range(0, dataset.table.height, eager=True)
    return prepare_records(
        dataset,
        InspectSettings(
            RecordMode(scope.mode.value),
            scope.start,
            scope.count,
            scope.seed,
        ),
        selection,
    ).positions


def _dimensions(
    records: pl.DataFrame, bins: int
) -> tuple[tuple[ImageHistogram, ...], tuple[ChannelSummary, ...]]:
    ready = records.filter(pl.col("status") == "Ready")
    charts: list[ImageHistogram] = []
    summaries: list[ChannelSummary] = []
    for name, label in (
        ("width", "Width"),
        ("height", "Height"),
        ("aspect_ratio", "Aspect ratio"),
    ):
        values = ready[name].to_numpy()
        moments = ChannelMoments()
        moments.add(values)
        summaries.append(
            moments.summary(ChannelKey("Dimensions", label, values.dtype.str))
        )
        if not len(values):
            charts.append(
                histogram(label, np.zeros(bins, dtype=np.float64), None, None)
            )
            continue
        assert moments.minimum is not None and moments.maximum is not None
        normalized = normalized_values(values, moments.minimum, moments.maximum)
        counts, _ = np.histogram(normalized, np.linspace(0, 1, bins + 1))
        charts.append(
            histogram(
                label, counts.astype(np.float64), moments.minimum, moments.maximum
            )
        )
    return tuple(charts), tuple(summaries)


def prepare_image_profile(
    dataset: Dataset,
    file_id: str,
    view_name: str,
    settings: ImageProfileSettings,
    selection: tuple[int, ...],
    references: ReferenceSettings,
    index: ReferenceIndex | None,
    arrays: ArrayStore,
    stop: Event,
    progress: ImageProgress,
    catalog: ArrayCatalog | None = None,
    mapping: ArrayRecordMapping | None = None,
) -> ImageProfile:
    settings.validate()
    if settings.column is None:
        raise ValueError("Choose an image field or confirmed image mapping")
    if mapping is not None:
        if catalog is None or mapping.layout != ArrayLayout.IMAGE:
            raise ValueError("Collection colors require a confirmed image mapping")
        mapping.record_count(catalog)
    elif dataset.table.schema.get(settings.column) != pl.String:
        raise ValueError("Image references require a physical String field")
    positions = image_positions(dataset, settings, selection)
    row_ids = dataset.row_ids
    references_column = dataset.table[settings.column] if mapping is None else None
    records: list[tuple[object, ...]] = []
    channel_records: list[tuple[object, ...]] = []
    successful: list[ProfileRecord] = []
    pooled: dict[ChannelKey, ChannelMoments] = {}
    total_pixels = profiled_pixels = 0
    images = ImageStore(retained_bytes=0)
    leases = ExitStack()
    try:
        if catalog is not None and mapping is not None and len(positions):
            # Keep the selected compressed member leased for both passes even
            # when it exceeds retention, avoiding one extraction per record.
            leases.enter_context(
                arrays.open_member(catalog, mapping.member, stop.is_set)
            )
        for number, position in enumerate(positions):
            check_cancelled(stop)
            row_id = int(row_ids[position])
            reference = (
                str(references_column[position])
                if references_column is not None
                and references_column[position] is not None
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
                record = profile_record(
                    locator, metadata, settings, images, arrays, stop
                )
                check_cancelled(stop)
                # Merge only after the source lease verifies this record.
                for name, moments in zip(
                    metadata.channels, record.moments, strict=True
                ):
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
                            str(summary.minimum)
                            if summary.minimum is not None
                            else None,
                            str(summary.maximum)
                            if summary.maximum is not None
                            else None,
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
                    record_row(
                        row_id, int(position), reference, "Unresolved", str(error)
                    )
                )
            except Exception as error:
                check_cancelled(stop)
                records.append(
                    record_row(row_id, int(position), reference, "Failed", str(error))
                )
        check_cancelled(stop)
        counts = {key: np.zeros(settings.bins, dtype=np.float64) for key in pooled}
        edges = np.linspace(0, 1, settings.bins + 1)
        for number, record in enumerate(successful):
            check_cancelled(stop)
            progress.update("Shared channel histograms", number, len(successful))
            locator, metadata = record.locator, record.metadata
            # Failure in pass two rejects the whole result: moments and bins
            # must describe the same source identities, not mixed snapshots.
            with original_pixels(
                locator, metadata.orientation, images, arrays, stop
            ) as raw:
                for batch in pixel_batches(raw, settings, locator.origin.row_id, stop):
                    for channel, name in enumerate(metadata.channels):
                        key = ChannelKey(metadata.mode, name, metadata.dtype.str)
                        bounds = pooled[key]
                        if bounds.minimum is not None and bounds.maximum is not None:
                            normalized = normalized_values(
                                batch[:, channel], bounds.minimum, bounds.maximum
                            )
                            bins, _ = np.histogram(normalized, edges)
                            counts[key] += bins
        check_cancelled(stop)
        record_frame = pl.DataFrame(records, schema=RECORD_SCHEMA, orient="row")
        channel_frame = pl.DataFrame(
            channel_records, schema=CHANNEL_SCHEMA, orient="row"
        )
        summaries = tuple(moments.summary(key) for key, moments in pooled.items())
        charts = tuple(
            histogram(key.label, counts[key], moments.minimum, moments.maximum)
            for key, moments in pooled.items()
        )
        statuses = record_frame["status"].to_list()
        dimensions, dimension_summaries = _dimensions(record_frame, settings.bins)
        progress.update("Image profile ready", len(positions), len(positions))
        return ImageProfile(
            file_id,
            view_name,
            dataset.revision,
            dataset.source,
            settings,
            mapping,
            dataset.table.height,
            record_frame,
            channel_frame,
            summaries,
            dimensions,
            charts,
            statuses.count("Ready"),
            statuses.count("Null"),
            statuses.count("Unresolved"),
            statuses.count("Failed"),
            total_pixels,
            profiled_pixels,
            dimension_summaries,
        )
    finally:
        try:
            leases.close()
        finally:
            images.cleanup()
