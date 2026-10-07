"""Bounded exact signal statistics, stable RMS and explicit original-unit thresholds."""

from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from typing import cast

import numpy as np
from numpy.typing import NDArray

from datelier.inspection.audio.profile_types import (
    AudioChannelSummary,
    AudioProgress,
    AudioSignalProfile,
    AudioThresholds,
)
from datelier.inspection.audio.reading import audio_blocks
from datelier.inspection.audio.types import AudioLocator, AudioMetadata, AudioRange
from datelier.io.arrays.storage import ArrayStore

type AudioScalar = np.integer | np.floating


def clipping_bounds(
    metadata: AudioMetadata, thresholds: AudioThresholds
) -> tuple[int | float, int | float]:
    if thresholds.clipping is not None:
        return -thresholds.clipping, thresholds.clipping
    if metadata.dtype.kind in "iu":
        limits = np.iinfo(metadata.dtype.str)
        return int(limits.min), int(limits.max)
    bits = {"PCM_U8": 8, "PCM_S8": 8, "PCM_16": 16, "PCM_24": 24, "PCM_32": 32}.get(
        metadata.subtype
    )
    return -1.0, 1.0 - 2.0 ** (1 - bits) if bits is not None else 1.0


class ChannelAccumulator:
    def __init__(self) -> None:
        self.samples = self.finite = self.clipped = self.silent = 0
        self.minimum: AudioScalar | None = None
        self.maximum: AudioScalar | None = None
        self.scale = np.longdouble(0)
        self.mean = np.longdouble(0)
        self.squares = np.longdouble(0)

    def add(
        self,
        raw: NDArray[np.generic],
        bounds: tuple[int | float, int | float],
        silence: float,
    ) -> None:
        self.samples += raw.size
        chosen = raw[np.isfinite(raw)]
        count = chosen.size
        if not count:
            return
        # Metadata validates real numeric dtypes before a signal scan.
        lo, hi = cast(AudioScalar, chosen.min()), cast(AudioScalar, chosen.max())
        self.minimum = lo if self.minimum is None else min(self.minimum, lo)
        self.maximum = hi if self.maximum is None else max(self.maximum, hi)
        values = np.asarray(chosen, dtype=np.longdouble)
        amplitudes = np.abs(values)
        scale = np.max(amplitudes)
        self.clipped += int(
            np.count_nonzero((values <= bounds[0]) | (values >= bounds[1]))
        )
        self.silent += int(np.count_nonzero(amplitudes <= silence))
        total = self.finite + count
        mean = (
            np.mean(values / scale, dtype=np.longdouble) * scale
            if scale
            else np.longdouble(0)
        )
        self.mean = self.mean * (np.longdouble(self.finite) / total) + mean * (
            np.longdouble(count) / total
        )
        if scale > self.scale:
            self.squares *= (self.scale / scale) ** 2
            self.scale = scale
        if self.scale:
            self.squares += np.sum((values / self.scale) ** 2, dtype=np.longdouble)
        self.finite = total

    def summary(self, channel: int) -> AudioChannelSummary:
        mean = float(self.mean) if self.finite else None
        rms = (
            float(self.scale * np.sqrt(self.squares / self.finite))
            if self.finite
            else None
        )
        representable = (mean is None or isfinite(mean)) and (
            rms is None or isfinite(rms)
        )
        peak = (
            max(abs(np.longdouble(self.minimum)), abs(np.longdouble(self.maximum)))
            if self.finite
            else None
        )
        return AudioChannelSummary(
            channel,
            self.samples,
            self.finite,
            self.samples - self.finite,
            str(self.minimum) if self.minimum is not None else None,
            str(self.maximum) if self.maximum is not None else None,
            str(peak) if peak is not None else None,
            mean if mean is None or isfinite(mean) else None,
            rms if rms is None or isfinite(rms) else None,
            self.clipped,
            self.silent,
            "Mean/RMS exceeds Float64 reporting range; original extrema retained."
            if not representable
            else "",
        )


@dataclass
class SilenceRuns:
    frames: int = 0
    longest: int = 0
    trailing: int = 0

    def add(self, silent: NDArray[np.bool_]) -> None:
        self.frames += int(np.count_nonzero(silent))
        # Boundaries avoid per-sample Python work and keep cross-block runs exact.
        edges = np.flatnonzero(np.diff(np.concatenate(([False], silent, [False]))))
        starts, stops = edges[::2], edges[1::2]
        if len(starts):
            lengths = stops - starts
            if starts[0] == 0:
                lengths[0] += self.trailing
            self.longest = max(self.longest, int(lengths.max()))
            self.trailing = int(lengths[-1]) if stops[-1] == len(silent) else 0
        else:
            self.trailing = 0


def profile_signal(
    locator: AudioLocator,
    metadata: AudioMetadata,
    selected: AudioRange,
    thresholds: AudioThresholds,
    arrays: ArrayStore,
    stopped: Callable[[], bool] | None = None,
    progress: AudioProgress | None = None,
    *,
    block_frames: int = 65536,
) -> AudioSignalProfile:
    thresholds.validate()
    metadata.require_rate()
    start, stop = selected.bounds(metadata.frames)
    bounds = clipping_bounds(metadata, thresholds)
    channels = tuple(ChannelAccumulator() for _ in range(metadata.channels))
    silence = SilenceRuns()
    nonfinite_frames = 0
    if progress is not None:
        progress.update(0, stop - start)
    with audio_blocks(
        locator, metadata, arrays, selected, block_frames=block_frames, stopped=stopped
    ) as blocks:
        for block in blocks:
            values = block.samples
            finite = np.isfinite(values).all(axis=1)
            nonfinite_frames += int(np.count_nonzero(~finite))
            silence.add(
                finite
                & (np.abs(values.astype(np.longdouble)) <= thresholds.silence).all(
                    axis=1
                )
            )
            for channel, accumulator in enumerate(channels):
                accumulator.add(values[:, channel], bounds, thresholds.silence)
            if progress is not None:
                progress.update(block.start + len(values) - start, stop - start)
    return AudioSignalProfile(
        locator,
        metadata,
        AudioRange(start, stop),
        thresholds,
        bounds,
        tuple(
            accumulator.summary(channel) for channel, accumulator in enumerate(channels)
        ),
        silence.frames,
        silence.longest,
        nonfinite_frames,
    )
