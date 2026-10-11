"""Explicit two-pass image profiles with reusable scans and physical bounds."""

from contextlib import ExitStack
from threading import Event

import numpy as np
import polars as pl

from datelier.core.dataset import Dataset
from datelier.inspection.arrays.mapping import ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.images.moments import histogram, normalized_values
from datelier.inspection.images.pixels import (
    check_cancelled,
    original_pixels,
    pixel_batches,
)
from datelier.inspection.images.profile_histograms import (
    bounds_for,
    dimension_histograms,
)
from datelier.inspection.images.profile_scan import (
    ImageProfileScan,
    scan_image_profile,
    validate_profile_input,
)
from datelier.inspection.images.profile_types import (
    ChannelKey,
    ImageBounds,
    ImageProfile,
    ImageProfileSettings,
    ImageProgress,
    ImageScopeMode,
)
from datelier.inspection.images.storage import ImageStore
from datelier.inspection.records.prepare import prepare_records
from datelier.inspection.records.types import InspectSettings, RecordMode
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays import ArrayStore


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
    validate_profile_input(dataset, settings, catalog, mapping)
    positions = image_positions(dataset, settings, selection)
    images = ImageStore(retained_bytes=0)
    try:
        with ExitStack() as leases:
            if catalog is not None and mapping is not None and len(positions):
                leases.enter_context(
                    arrays.open_member(catalog, mapping.member, stop.is_set)
                )
            scan = scan_image_profile(
                dataset,
                file_id,
                view_name,
                settings,
                positions,
                references,
                index,
                images,
                arrays,
                stop,
                progress,
                catalog,
                mapping,
            )
            return finish_image_profile(scan, images, arrays, stop, progress)
    finally:
        images.cleanup()


def finish_image_profile(
    scan: ImageProfileScan,
    images: ImageStore,
    arrays: ArrayStore,
    stop: Event,
    progress: ImageProgress,
    shared_bounds: ImageBounds | None = None,
) -> ImageProfile:
    dataset, settings, mapping = scan.dataset, scan.settings, scan.mapping
    file_id, view_name = scan.file_id, scan.view_name
    successful, pooled = scan.successful, scan.pooled
    total_pixels, profiled_pixels = scan.total_pixels, scan.profiled_pixels
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
                    lo, hi = bounds_for(key, pooled[key], shared_bounds)
                    if lo is not None and hi is not None:
                        normalized = normalized_values(batch[:, channel], lo, hi)
                        bins, _ = np.histogram(normalized, edges)
                        counts[key] += bins
    check_cancelled(stop)
    record_frame, channel_frame = scan.records, scan.channel_records
    summaries = tuple(moments.summary(key) for key, moments in pooled.items())
    charts = tuple(
        histogram(key.label, counts[key], *bounds_for(key, moments, shared_bounds))
        for key, moments in pooled.items()
    )
    statuses = record_frame["status"].to_list()
    dimensions, dimension_summaries = dimension_histograms(
        record_frame, settings.bins, shared_bounds
    )
    progress.update("Image profile ready", len(scan.records), len(scan.records))
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
