"""Signal-view recipes and bounded source-aligned worker results."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

import numpy as np
from numpy.typing import NDArray

from datelier.inspection.audio.types import AudioLocator, AudioMetadata, AudioRange


class AudioViewKind(StrEnum):
    WAVEFORM = "Waveform"
    SPECTROGRAM = "Spectrogram"


class SpectrumScale(StrEnum):
    POWER = "Linear power density"
    DECIBELS = "Decibels"


class AudioWindow(StrEnum):
    HANN = "Hann"
    HAMMING = "Hamming"
    RECTANGULAR = "Rectangular"

    @property
    def scipy_name(self) -> str:
        return {self.HANN: "hann", self.HAMMING: "hamming", self.RECTANGULAR: "boxcar"}[
            self
        ]


@dataclass(frozen=True)
class SignalViewSettings:
    kind: AudioViewKind = AudioViewKind.WAVEFORM
    waveform_bins: int = 2048
    fft: int = 1024
    hop: int = 256
    window: AudioWindow = AudioWindow.HANN
    frequency_low: float = 0
    frequency_high: float | None = None
    scale: SpectrumScale = SpectrumScale.DECIBELS
    db_floor: float = -120
    time_bins: int = 2048
    frequency_bins: int = 1024

    def validate(self) -> None:
        if (
            self.kind not in AudioViewKind
            or self.window not in AudioWindow
            or self.scale not in SpectrumScale
        ):
            raise ValueError("Unknown audio signal view, window or scale")
        if not 1 <= self.waveform_bins <= 65536:
            raise ValueError("Waveform displays require 1–65536 envelope bins")
        if not 16 <= self.fft <= 65536 or self.fft & (self.fft - 1):
            raise ValueError("FFT length must be a power of two from 16 to 65536")
        if not 1 <= self.hop <= self.fft:
            raise ValueError("FFT hop must be between 1 and the FFT length")
        if not isfinite(self.frequency_low) or self.frequency_low < 0:
            raise ValueError("Minimum frequency must be finite and nonnegative")
        if self.frequency_high is not None and (
            not isfinite(self.frequency_high)
            or self.frequency_high <= self.frequency_low
        ):
            raise ValueError("Maximum frequency must be finite and above the minimum")
        if not isfinite(self.db_floor) or not -300 <= self.db_floor < 0:
            raise ValueError("Decibel floor must be from −300 to below 0 dB")
        if not 1 <= self.time_bins <= 16384 or not 1 <= self.frequency_bins <= 32769:
            raise ValueError("Spectral display bins exceed supported bounds")


@dataclass(frozen=True)
class WaveformEnvelope:
    locator: AudioLocator
    metadata: AudioMetadata
    range: AudioRange
    channel: int
    settings: SignalViewSettings
    starts: NDArray[np.int64]
    stops: NDArray[np.int64]
    minimum: NDArray[np.generic]
    maximum: NDArray[np.generic]
    finite: NDArray[np.uint64]
    times: NDArray[np.float64]
    plot_minimum: NDArray[np.float64]
    plot_maximum: NDArray[np.float64]
    nonfinite: int
    bin_frames: int

    @property
    def retained_bytes(self) -> int:
        return sum(
            array.nbytes
            for array in (
                self.starts,
                self.stops,
                self.minimum,
                self.maximum,
                self.finite,
                self.times,
                self.plot_minimum,
                self.plot_maximum,
            )
        )


@dataclass(frozen=True)
class SpectralView:
    locator: AudioLocator
    metadata: AudioMetadata
    range: AudioRange
    channel: int
    settings: SignalViewSettings
    power: NDArray[np.float64]  # One-sided PSD, original amplitude units²/Hz.
    values: NDArray[np.float64]  # Display-only scale; frequency × time.
    times: NDArray[np.float64]
    frequencies: NDArray[np.float64]
    time_step: int
    frequency_step: int
    spectral_frames: int
    window_frames: int
    tail_frames: int
    nonfinite: int
    time_bounds: tuple[float, float]
    frequency_bounds: tuple[float, float]

    @property
    def retained_bytes(self) -> int:
        return (
            self.power.nbytes
            + (0 if self.values is self.power else self.values.nbytes)
            + self.times.nbytes
            + self.frequencies.nbytes
        )

    @property
    def aggregated(self) -> bool:
        return self.time_step > 1 or self.frequency_step > 1


type PreparedSignalView = WaveformEnvelope | SpectralView
