"""Streaming original extrema per display bin; full-resolution windows stay separate."""

from collections.abc import Callable
from math import ceil
from typing import cast

import numpy as np
from numpy.typing import NDArray

from datelier.inspection.audio.profile_types import AudioProgress
from datelier.inspection.audio.reading import audio_blocks
from datelier.inspection.audio.types import AudioLocator, AudioMetadata, AudioRange
from datelier.inspection.audio.view_types import SignalViewSettings, WaveformEnvelope
from datelier.io.arrays.storage import ArrayStore


def prepare_waveform(
    locator: AudioLocator,
    metadata: AudioMetadata,
    selected: AudioRange,
    channel: int,
    settings: SignalViewSettings,
    arrays: ArrayStore,
    cpu_bytes: int = 16 * 1024 * 1024,
    stopped: Callable[[], bool] | None = None,
    progress: AudioProgress | None = None,
) -> WaveformEnvelope:
    settings.validate()
    rate = metadata.require_rate()
    if not 0 <= channel < metadata.channels:
        raise ValueError("Waveform channel is outside the original signal")
    start, stop = selected.bounds(metadata.frames)
    frames = stop - start
    if not frames:
        raise ValueError("Choose a nonempty waveform range")
    per_bin = 48 + metadata.dtype.itemsize * 2
    bins = min(settings.waveform_bins, cpu_bytes // per_bin, frames)
    if bins < 1:
        raise ValueError("Waveform CPU budget cannot hold one envelope bin")
    width = ceil(frames / bins)
    starts = np.arange(start, stop, width, dtype=np.int64)
    stops = np.minimum(starts + width, stop)
    minimum = cast(NDArray[np.generic], np.zeros(len(starts), dtype=metadata.dtype))
    maximum = minimum.copy()
    finite = np.zeros(len(starts), dtype=np.uint64)
    nonfinite = 0
    if progress is not None:
        progress.update(0, frames)
    with audio_blocks(
        locator, metadata, arrays, selected, stopped=stopped, channel=channel
    ) as blocks:
        for block in blocks:
            raw = block.samples[:, 0]
            offset = 0
            while offset < len(raw):
                index = (block.start + offset - start) // width
                count = min(len(raw) - offset, int(stops[index]) - block.start - offset)
                values = raw[offset : offset + count]
                chosen = values[np.isfinite(values)]
                nonfinite += count - chosen.size
                if chosen.size:
                    lo, hi = chosen.min(), chosen.max()
                    minimum[index] = min(minimum[index], lo) if finite[index] else lo
                    maximum[index] = max(maximum[index], hi) if finite[index] else hi
                    finite[index] += chosen.size
                offset += count
            if progress is not None:
                progress.update(block.start + len(raw) - start, frames)
    times = (starts.astype(np.float64) + (stops - starts - 1) / 2) / rate
    with np.errstate(over="ignore"):
        lower = minimum.astype(np.float64)
        upper = maximum.astype(np.float64)
    if np.any((finite > 0) & (~np.isfinite(lower) | ~np.isfinite(upper))):
        raise ValueError(
            "Waveform exceeds Float64 plotting range; inspect original sample values"
        )
    lower[finite == 0] = upper[finite == 0] = np.nan
    for array in (starts, stops, minimum, maximum, finite, times, lower, upper):
        array.flags.writeable = False
    return WaveformEnvelope(
        locator,
        metadata,
        AudioRange(start, stop),
        channel,
        settings,
        starts,
        stops,
        minimum,
        maximum,
        finite,
        times,
        lower,
        upper,
        nonfinite,
        width,
    )
