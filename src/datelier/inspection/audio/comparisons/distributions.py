"""Common-bin finite scalar curves; amplitude families never mix physical units."""

from math import isfinite

import numpy as np
import polars as pl
from numpy.typing import NDArray

from datelier.inspection.audio.collections.types import AudioCollectionProfile
from datelier.inspection.audio.comparisons.types import (
    AudioComparisonCurve,
    AudioMetric,
    AudioScalarSummary,
)

RECORD_METRICS = (
    AudioMetric("Duration", "duration", "seconds"),
    AudioMetric("Sample rate", "sample_rate", "Hz"),
    AudioMetric("Frames", "frames", "sample frames"),
    AudioMetric("Channels", "channels", "channels"),
    AudioMetric("Silent frames", "silence_fraction", "fraction of all frames"),
    AudioMetric("Longest silence", "longest_silence", "seconds"),
    AudioMetric("Nonfinite frames", "nonfinite_fraction", "fraction of all frames"),
)
CHANNEL_METRICS = (("Mean", "mean"), ("RMS", "rms"), ("Peak", "peak"))


def metrics(profiles: tuple[AudioCollectionProfile, ...]) -> tuple[AudioMetric, ...]:
    chosen = list(RECORD_METRICS)
    families: dict[tuple[str, int], None] = {}
    channels: dict[int, None] = {}
    for profile in profiles:
        for family, channel in (
            profile.channel_records.select("family", "channel").unique().iter_rows()
        ):
            families[str(family), int(channel)] = None
            channels[int(channel)] = None
    for family, channel in sorted(families):
        chosen.extend(
            AudioMetric(name, field, family, channel) for name, field in CHANNEL_METRICS
        )
    for channel in sorted(channels):
        chosen.extend(
            (
                AudioMetric(
                    "Clipped samples",
                    "clipped_fraction",
                    "fraction of finite samples",
                    channel,
                ),
                AudioMetric(
                    "Silent samples",
                    "silent_fraction",
                    "fraction of finite samples",
                    channel,
                ),
            )
        )
    return tuple(chosen)


def metric_records(
    profile: AudioCollectionProfile, metric: AudioMetric
) -> pl.DataFrame:
    if metric.channel is None:
        return profile.records.filter(pl.col("status") == "Ready")
    records = profile.channel_records.filter(pl.col("channel") == metric.channel)
    if metric.field in ("mean", "rms", "peak"):
        records = records.filter(pl.col("family") == metric.family)
    return records


def normalized_values(
    values: NDArray[np.float64], lo: float, hi: float
) -> NDArray[np.longdouble]:
    raw = values.astype(np.longdouble)
    if lo == hi:
        return np.full(len(raw), 0.5, dtype=np.longdouble)
    return (raw - np.longdouble(lo)) / (np.longdouble(hi) - np.longdouble(lo))


def prepare_curve(
    profiles: tuple[AudioCollectionProfile, ...], metric: AudioMetric, bins: int
) -> AudioComparisonCurve:
    values: list[NDArray[np.float64] | None] = []
    summaries: list[AudioScalarSummary | None] = []
    for profile in profiles:
        records = metric_records(profile, metric)
        if metric.channel is not None and not records.height:
            values.append(None)
            summaries.append(None)
            continue
        finite = records[metric.field].drop_nulls().cast(pl.Float64)
        finite = finite.filter(finite.is_finite())
        raw = finite.to_numpy()
        values.append(raw)
        if len(raw):
            lo, hi = float(raw.min()), float(raw.max())
            scale = max(abs(lo), abs(hi))
            mean = (
                float(np.mean(raw.astype(np.longdouble) / scale) * scale)
                if scale
                else 0.0
            )
            summaries.append(AudioScalarSummary(len(raw), lo, hi, mean))
        else:
            summaries.append(AudioScalarSummary(0, None, None, None))
    lows = [s.minimum for s in summaries if s is not None and s.minimum is not None]
    highs = [s.maximum for s in summaries if s is not None and s.maximum is not None]
    lo, hi = (min(lows), max(highs)) if lows else (None, None)
    scaled = (
        lo is not None
        and hi is not None
        and (max(abs(lo), abs(hi)) > 1e100 or not isfinite(hi - lo))
    )
    edges = np.linspace(0, 1, bins + 1)
    if lo is not None and hi is not None and not scaled:
        if lo == hi:
            padding = max(abs(lo) * 0.05, 0.5)
            edges = np.linspace(lo - padding, hi + padding, bins + 1)
        else:
            edges = np.linspace(lo, hi, bins + 1)
    counts, proportions = [], []
    for raw in values:
        if raw is None:
            counts.append(None)
            proportions.append(None)
            continue
        hist = np.zeros(bins, dtype=np.float64)
        if len(raw) and lo is not None and hi is not None:
            hist[:] = np.histogram(
                normalized_values(raw, lo, hi) if scaled else raw, bins=edges
            )[0]
        # Prepared pre-step paths include zero at both edges. No arrays in frames.
        path = np.concatenate(([0.0], hist, [0.0]))
        counts.append(path)
        proportions.append(path / len(raw) if len(raw) else path.copy())
    plot_x = np.concatenate((edges, [edges[-1]]))
    for array in (
        edges,
        plot_x,
        *(a for a in (*counts, *proportions) if a is not None),
    ):
        array.flags.writeable = False
    return AudioComparisonCurve(
        metric,
        lo,
        hi,
        scaled,
        edges,
        plot_x,
        tuple(counts),
        tuple(proportions),
        tuple(summaries),
    )
