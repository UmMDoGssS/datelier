"""Streaming PSD/mel band-power grids with explicit peak aggregation and scales."""

from collections.abc import Callable
from math import ceil

import numpy as np

from datelier.inspection.audio.profiles import AudioProgress
from datelier.inspection.audio.signal.display import spectral_display
from datelier.inspection.audio.signal.frames import power_frames
from datelier.inspection.audio.signal.mel import mel_filters
from datelier.inspection.audio.signal.types import (
    AudioViewKind,
    SignalViewSettings,
    SpectralView,
)
from datelier.inspection.audio.types import AudioLocator, AudioMetadata, AudioRange
from datelier.io.arrays import ArrayStore


def prepare_spectrogram(
    locator: AudioLocator,
    metadata: AudioMetadata,
    selected: AudioRange,
    channel: int,
    settings: SignalViewSettings,
    arrays: ArrayStore,
    cpu_bytes: int = 16 * 1024 * 1024,
    stopped: Callable[[], bool] | None = None,
    progress: AudioProgress | None = None,
) -> SpectralView:
    settings.validate()
    rate = metadata.require_rate()
    start, stop = selected.bounds(metadata.frames)
    window = min(settings.fft, stop - start)
    if window < 1 or not 0 <= channel < metadata.channels:
        raise ValueError("Choose a nonempty spectral range and an available channel")
    high = min(
        settings.frequency_high if settings.frequency_high is not None else rate / 2,
        rate / 2,
    )
    if settings.frequency_low >= high:
        raise ValueError("Frequency range lies outside the original Nyquist frequency")
    frequencies = np.fft.rfftfreq(settings.fft, 1 / rate)
    indices = np.flatnonzero(
        (frequencies >= settings.frequency_low) & (frequencies <= high)
    )
    if not len(indices) and settings.mode != AudioViewKind.MEL:
        raise ValueError(
            "Frequency range contains no FFT bins; widen it or increase FFT length"
        )
    spectral_frames = 1 + (stop - start - window) // settings.hop
    bank = (
        mel_filters(
            rate, settings.fft, settings.mel_bands, settings.frequency_low, high
        )
        if settings.mode == AudioViewKind.MEL
        else None
    )
    frequency_step = (
        1 if bank is not None else ceil(len(indices) / settings.frequency_bins)
    )
    rows = (
        settings.mel_bands if bank is not None else ceil(len(indices) / frequency_step)
    )
    # Two Float64 grids and RGBA, plus both Float64 axes. Even a full
    # 32,769-frequency axis must stay inside the configured retained budget.
    maximum_columns = (cpu_bytes - rows * 8) // (rows * 20 + 8)
    columns = min(settings.time_bins, spectral_frames, maximum_columns)
    if columns < 1:
        raise ValueError(
            "Spectral CPU budget cannot hold a frequency column; "
            "narrow the frequency range"
        )
    time_step = ceil(spectral_frames / columns)
    columns = ceil(spectral_frames / time_step)
    power = np.zeros((rows, columns), dtype=np.float64)
    frequency_starts = np.arange(0, len(indices), frequency_step)
    with power_frames(
        locator, metadata, selected, channel, settings, arrays, stopped, progress
    ) as scan:
        for index, values in enumerate(scan.frames):
            grouped = (
                bank.apply(values)
                if bank is not None
                else np.maximum.reduceat(values[indices], frequency_starts)
            )
            if not np.isfinite(grouped).all():
                raise ValueError(
                    "Mel band power exceeds Float64 range; inspect original values"
                )
            np.maximum(
                power[:, index // time_step], grouped, out=power[:, index // time_step]
            )
    nonfinite = scan.nonfinite
    values, tiles, color_bounds = spectral_display(power, settings)
    time_starts = np.arange(0, spectral_frames, time_step, dtype=np.int64)
    time_counts = np.minimum(time_step, spectral_frames - time_starts)
    times = (
        start + window / 2 + (time_starts + (time_counts - 1) / 2) * settings.hop
    ) / rate
    frequencies = (
        bank.centers
        if bank is not None
        else np.array(
            [
                frequencies[indices[i : i + frequency_step]].mean()
                for i in range(0, len(indices), frequency_step)
            ]
        )
    )
    time_width = settings.hop * time_step / rate
    frequency_width = rate / settings.fft * frequency_step
    time_bounds = (
        (start + window / 2 - settings.hop / 2) / rate,
        (start + window / 2 - settings.hop / 2) / rate + columns * time_width,
    )
    frequency_bounds = (
        bank.bounds
        if bank is not None
        else (
            float(indices[0] * rate / settings.fft - rate / settings.fft / 2),
            float(
                indices[0] * rate / settings.fft
                - rate / settings.fft / 2
                + rows * frequency_width
            ),
        )
    )
    for array in (power, values, times, frequencies):
        array.flags.writeable = False
    return SpectralView(
        locator,
        metadata,
        AudioRange(start, stop),
        channel,
        settings,
        power,
        values,
        times,
        frequencies,
        time_step,
        frequency_step,
        spectral_frames,
        window,
        (stop - start - window) % settings.hop,
        nonfinite,
        time_bounds,
        frequency_bounds,
        tiles,
        color_bounds,
        (int(power.argmax()) // columns, int(power.argmax()) % columns),
        bank.empty if bank is not None else 0,
    )
