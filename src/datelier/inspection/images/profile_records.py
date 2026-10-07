"""Transactional per-record image moments and provenance rows."""

from dataclasses import dataclass
from threading import Event

import polars as pl

from datelier.inspection.images.moments import ChannelMoments
from datelier.inspection.images.pixels import original_pixels, pixel_batches
from datelier.inspection.images.profile_types import ImageProfileSettings
from datelier.inspection.images.storage import ImageStore
from datelier.inspection.images.types import ImageLocator, ImageMetadata
from datelier.io.arrays.storage import ArrayStore

RECORD_SCHEMA = {
    "row_id": pl.UInt64,
    "position": pl.UInt64,
    "status": pl.String,
    "reference": pl.String,
    "asset": pl.String,
    "width": pl.UInt64,
    "height": pl.UInt64,
    "aspect_ratio": pl.Float64,
    "mode": pl.String,
    "dtype": pl.String,
    "orientation": pl.UInt8,
    "pixels": pl.UInt64,
    "profiled_pixels": pl.UInt64,
    "nonfinite": pl.UInt64,
    "size_bytes": pl.UInt64,
    "modified_ns": pl.UInt64,
    "diagnostic": pl.String,
}
CHANNEL_SCHEMA = {
    "row_id": pl.UInt64,
    "mode": pl.String,
    "channel": pl.String,
    "dtype": pl.String,
    "values": pl.UInt64,
    "finite": pl.UInt64,
    "nonfinite": pl.UInt64,
    "minimum": pl.String,
    "maximum": pl.String,
    "mean": pl.Float64,
    "stddev": pl.Float64,
}


@dataclass(frozen=True)
class ProfileRecord:
    locator: ImageLocator
    metadata: ImageMetadata
    moments: tuple[ChannelMoments, ...]
    profiled_pixels: int


def profile_record(
    locator: ImageLocator,
    metadata: ImageMetadata,
    settings: ImageProfileSettings,
    images: ImageStore,
    arrays: ArrayStore,
    stop: Event,
) -> ProfileRecord:
    moments = tuple(ChannelMoments() for _ in metadata.channels)
    counted = 0
    with original_pixels(locator, metadata.orientation, images, arrays, stop) as raw:
        for batch in pixel_batches(raw, settings, locator.origin.row_id, stop):
            counted += batch.shape[0]
            for channel, accumulator in enumerate(moments):
                accumulator.add(batch[:, channel])
    return ProfileRecord(locator, metadata, moments, counted)


def record_row(
    row_id: int,
    position: int,
    reference: str | None,
    status: str,
    diagnostic: str = "",
    record: ProfileRecord | None = None,
) -> tuple[object, ...]:
    fields: dict[str, object] = dict.fromkeys(RECORD_SCHEMA)
    fields.update(
        row_id=row_id,
        position=position,
        reference=reference,
        status=status,
        diagnostic=diagnostic,
        pixels=0,
        profiled_pixels=0,
        nonfinite=0,
    )
    if record is not None:
        locator, metadata = record.locator, record.metadata
        asset = locator.asset
        source = locator.catalog.source if locator.catalog is not None else None
        fields.update(
            asset=str(asset.path) if asset else str(source.path) if source else None,
            width=metadata.width,
            height=metadata.height,
            aspect_ratio=metadata.aspect_ratio,
            mode=metadata.mode,
            dtype=metadata.dtype.str,
            orientation=metadata.orientation,
            pixels=metadata.width * metadata.height,
            profiled_pixels=record.profiled_pixels,
            nonfinite=sum(m.values - m.finite for m in record.moments),
            size_bytes=asset.size if asset else source.size_bytes if source else None,
            modified_ns=asset.modified_ns
            if asset
            else source.modified_ns
            if source
            else None,
        )
    return tuple(fields[name] for name in RECORD_SCHEMA)
