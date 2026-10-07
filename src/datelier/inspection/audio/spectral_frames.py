"""Bounded original-rate FFT frames without whole-record signal copies."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import cast

import numpy as np
from numpy.typing import NDArray
from scipy.fft import rfft
from scipy.signal import get_window

from datelier.inspection.audio.profile_types import AudioProgress
from datelier.inspection.audio.reading import BLOCK_FRAMES, audio_blocks, check_stopped
from datelier.inspection.audio.types import AudioLocator, AudioMetadata, AudioRange
from datelier.inspection.audio.view_types import SignalViewSettings
from datelier.io.arrays.storage import ArrayStore


@dataclass
class SpectralScan:
    frames: Iterator[NDArray[np.float64]]
    nonfinite: int = 0


@contextmanager
def power_frames(
    locator: AudioLocator,
    metadata: AudioMetadata,
    selected: AudioRange,
    channel: int,
    settings: SignalViewSettings,
    arrays: ArrayStore,
    stopped: Callable[[], bool] | None = None,
    progress: AudioProgress | None = None,
) -> Iterator[SpectralScan]:
    """No detrending/resampling. Short windows zero-pad only the FFT, not samples.

    Complete windows start at the chosen frame and advance by hop. At most
    hop−1 trailing samples are outside a complete window; callers report this.
    Nonfinite input samples become zero solely in the spectral display.
    """
    start, stop = selected.bounds(metadata.frames)
    window_frames = min(settings.fft, stop - start)
    if window_frames < 1 or not 0 <= channel < metadata.channels:
        raise ValueError("Choose a nonempty spectral range and an available channel")
    rate = metadata.require_rate()
    window = cast(
        NDArray[np.float64],
        get_window(settings.window.scipy_name, window_frames, fftbins=True),
    )
    normalization = rate * float(np.square(window).sum())
    pending = np.empty(window_frames + BLOCK_FRAMES, dtype=np.float64)
    length = 0
    if progress is not None:
        progress.update(0, stop - start)
    with audio_blocks(
        locator, metadata, arrays, selected, stopped=stopped, channel=channel
    ) as blocks:

        def frames() -> Iterator[NDArray[np.float64]]:
            nonlocal length
            for block in blocks:
                check_stopped(stopped)
                raw = block.samples[:, 0]
                scan.nonfinite += int(np.count_nonzero(~np.isfinite(raw)))
                with np.errstate(over="ignore"):
                    converted = raw.astype(np.float64)
                if np.any(np.isfinite(raw) & ~np.isfinite(converted)):
                    raise ValueError(
                        "Samples exceed Float64 spectral range; inspect original values"
                    )
                converted = np.nan_to_num(converted, nan=0, posinf=0, neginf=0)
                pending[length : length + len(converted)] = converted
                length += len(converted)
                offset = 0
                while length - offset >= window_frames:
                    check_stopped(stopped)
                    transformed = rfft(
                        pending[offset : offset + window_frames] * window,
                        n=settings.fft,
                    )
                    with np.errstate(over="ignore", invalid="ignore"):
                        power = np.asarray(
                            (transformed.real**2 + transformed.imag**2) / normalization,
                            dtype=np.float64,
                        )
                        power[1:-1] *= 2  # DC/Nyquist remain single-sided.
                    if not np.isfinite(power).all():
                        raise ValueError(
                            "Spectral power exceeds Float64 range; "
                            "original samples remain available"
                        )
                    yield power
                    offset += settings.hop
                # For a short record hop can exceed its only window; no later
                # block exists. Long records have window_frames == FFT >= hop.
                offset = min(offset, length)
                length -= offset
                pending[:length] = pending[offset : offset + length]
                if progress is not None:
                    progress.update(block.start + len(raw) - start, stop - start)

        scan = SpectralScan(frames())
        yield scan
