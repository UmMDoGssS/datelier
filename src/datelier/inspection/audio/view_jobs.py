"""Visible-signal work independent of record/profile/sample preparation."""

from concurrent.futures import Executor, Future
from dataclasses import replace
from threading import Event

import numpy as np

from datelier.core.jobs import JobExecutor
from datelier.inspection.audio.profile_types import AudioProgress
from datelier.inspection.audio.spectra import prepare_spectrogram
from datelier.inspection.audio.types import AudioLocator, AudioMetadata, AudioRange
from datelier.inspection.audio.view_types import (
    AudioViewKind,
    PreparedSignalView,
    SignalViewSettings,
    SpectralView,
    SpectrumScale,
)
from datelier.inspection.audio.waveforms import prepare_waveform
from datelier.io.arrays.storage import ArrayStore


def computation_settings(settings: SignalViewSettings) -> SignalViewSettings:
    if settings.kind == AudioViewKind.WAVEFORM:
        return SignalViewSettings(waveform_bins=settings.waveform_bins)
    return replace(
        settings, waveform_bins=2048, scale=SpectrumScale.POWER, db_floor=-120
    )


def rescale_spectrum(view: SpectralView, settings: SignalViewSettings) -> SpectralView:
    values = (
        view.power
        if settings.scale == SpectrumScale.POWER
        else np.maximum(
            10 * np.log10(np.maximum(view.power, 10 ** (settings.db_floor / 10))),
            settings.db_floor,
        )
    )
    values.flags.writeable = False
    return replace(view, values=values, settings=settings)


class SignalViewJobs:
    def __init__(self, executor: Executor | None = None) -> None:
        self._jobs = JobExecutor(
            executor, max_workers=1, name="audio-view", priority=-10
        )
        self._source: tuple[AudioLocator, AudioMetadata] | None = None
        self._future: Future[PreparedSignalView] | None = None
        self._requested: tuple[AudioRange, int, SignalViewSettings, int] | None = None
        self._stop = Event()
        self.active: PreparedSignalView | None = None
        self.progress = AudioProgress()
        self.message = "Choose a signal view."
        self.closed = False

    @property
    def busy(self) -> bool:
        return self._future is not None

    def bind(self, source: tuple[AudioLocator, AudioMetadata] | None) -> None:
        if self.closed:
            return
        if source != self._source:
            self.abandon()
            self._source = source

    def request(
        self,
        selected: AudioRange,
        channel: int,
        settings: SignalViewSettings,
        arrays: ArrayStore,
        cpu_bytes: int,
    ) -> None:
        if self.closed or self._source is None:
            return
        settings.validate()
        selected.bounds(self._source[1].frames)
        self._source[1].require_rate()
        relevant = computation_settings(settings)
        if settings.kind == AudioViewKind.SPECTROGRAM:
            relevant = replace(
                relevant,
                scale=settings.scale,
                db_floor=settings.db_floor
                if settings.scale == SpectrumScale.DECIBELS
                else -120,
            )
        requested = (selected, channel, relevant, cpu_bytes)
        if requested == self._requested:
            return
        previous = self.active
        can_rescale = (
            isinstance(previous, SpectralView)
            and self._requested is not None
            and self._requested[:2] == requested[:2]
            and self._requested[3] == cpu_bytes
            and computation_settings(previous.settings)
            == computation_settings(settings)
        )
        self.abandon()
        self._stop = Event()
        self._requested = requested
        self.progress = AudioProgress()
        if can_rescale and isinstance(previous, SpectralView):
            self._future = self._jobs.submit(rescale_spectrum, previous, settings)
        else:
            prepare = (
                prepare_waveform
                if settings.kind == AudioViewKind.WAVEFORM
                else prepare_spectrogram
            )
            self._future = self._jobs.submit(
                prepare,
                *self._source,
                selected,
                channel,
                settings,
                arrays,
                cpu_bytes,
                self._stop.is_set,
                self.progress,
            )
        self.message = f"Preparing {settings.kind.lower()}…"

    def poll(self) -> None:
        if self.closed or self._future is None or not self._future.done():
            return
        future, self._future = self._future, None
        try:
            self.active = future.result()
            self.message = "Signal view ready; original sample rate preserved."
        except Exception as error:
            self.message = f"Signal view failed: {error}. Retry this view."

    def abandon(self) -> None:
        self._stop.set()
        if self._future is not None:
            self._future.cancel()
        self._future = None
        self._requested = None
        self.active = None

    def close(self) -> None:
        self.closed = True
        self.abandon()
        self._source = None
        self._jobs.shutdown(wait=False, cancel_futures=True)
