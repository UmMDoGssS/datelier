"""Prepared scalar schemas and original-unit finite-value denominators."""

from math import isfinite

import polars as pl

from datelier.inspection.audio.profile_types import AudioSignalProfile

RECORD_SCHEMA = {
    "row_id": pl.UInt64,
    "position": pl.UInt64,
    "reference": pl.String,
    "status": pl.String,
    "diagnostic": pl.String,
    "frames": pl.UInt64,
    "channels": pl.UInt32,
    "sample_rate": pl.UInt32,
    "duration": pl.Float64,
    "silence_fraction": pl.Float64,
    "longest_silence": pl.Float64,
    "nonfinite_fraction": pl.Float64,
}
CHANNEL_SCHEMA = {
    "row_id": pl.UInt64,
    "channel": pl.UInt32,
    "family": pl.String,
    "dtype": pl.String,
    "samples": pl.UInt64,
    "finite": pl.UInt64,
    "nonfinite": pl.UInt64,
    "minimum": pl.String,
    "maximum": pl.String,
    "peak_original": pl.String,
    "mean": pl.Float64,
    "rms": pl.Float64,
    "peak": pl.Float64,
    "clipped_fraction": pl.Float64,
    "silent_fraction": pl.Float64,
    "clipping_low": pl.String,
    "clipping_high": pl.String,
    "silence_threshold": pl.Float64,
    "diagnostic": pl.String,
}


def fraction(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def channel_rows(profile: AudioSignalProfile) -> list[tuple[object, ...]]:
    metadata = profile.metadata
    family = metadata.units
    if profile.locator.catalog is not None:
        family += f" · {metadata.dtype}"
    rows: list[tuple[object, ...]] = []
    for channel in profile.channels:
        peak = float(channel.peak) if channel.peak is not None else None
        diagnostic = channel.diagnostic
        if peak is not None and not isfinite(peak):
            peak = None
            diagnostic += (
                " Peak exceeds Float64 plotting range; original value retained."
            )
        rows.append(
            (
                profile.locator.origin.row_id,
                channel.channel,
                family,
                metadata.dtype.str,
                channel.samples,
                channel.finite,
                channel.nonfinite,
                channel.minimum,
                channel.maximum,
                channel.peak,
                channel.mean,
                channel.rms,
                peak,
                fraction(channel.clipped, channel.finite),
                fraction(channel.silent, channel.finite),
                str(profile.clipping_bounds[0]),
                str(profile.clipping_bounds[1]),
                profile.thresholds.silence,
                diagnostic.strip(),
            )
        )
    return rows
