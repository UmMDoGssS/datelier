"""Original extrema, PSD normalization, exact axes, bounded aggregation and leases."""

from concurrent.futures import CancelledError
from dataclasses import replace
from pathlib import Path
from threading import Event

import numpy as np
import pytest
import soundfile as sf
from scipy.signal import get_window, stft

from datelier.inspection.arrays.mapping import ArrayLayout, ArrayRecordMapping
from datelier.inspection.audio.sources import audio_metadata, locate_audio
from datelier.inspection.audio.spectra import prepare_spectrogram
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.audio.view_types import (
    AudioViewKind,
    AudioWindow,
    SignalViewSettings,
    SpectrumScale,
)
from datelier.inspection.audio.waveforms import prepare_waveform
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.records import prepare_array_records
from datelier.io.arrays.storage import ArrayStore
from datelier.io.media import load_media


@pytest.mark.parametrize("bins", [1, 7, 1000])
def test_envelopes_keep_original_extrema_and_frame_centers(
    tmp_path: Path, bins: int
) -> None:
    path = tmp_path / "signal.wav"
    samples = np.zeros((100001, 2))
    samples[111, 0], samples[65537, 0], samples[99000, 0] = -3, 9, np.nan
    samples[:, 1] = 0.5
    sf.write(path, samples, 8000, subtype="DOUBLE")
    original = path.read_bytes()
    dataset = load_media(path).dataset
    locator = locate_audio(dataset, "f", "v", "path", 0, ReferenceSettings(), None)
    metadata = audio_metadata(locator)
    store = ArrayStore()
    try:
        result = prepare_waveform(
            locator,
            metadata,
            AudioRange(17, 100000),
            0,
            SignalViewSettings(waveform_bins=bins),
            store,
        )
        assert (
            result.nonfinite == 1
            and result.minimum.astype(np.float64).min() == -3
            and result.maximum.astype(np.float64).max() == 9
        )
        assert sum(result.finite) == 100000 - 17 - 1
        assert (
            len(result.times) <= bins
            and result.starts[0] == 17
            and result.stops[-1] == 100000
        )
        np.testing.assert_allclose(
            result.times,
            (result.starts + (result.stops - result.starts - 1) / 2) / 8000,
        )
        for i, (start, stop) in enumerate(
            zip(result.starts, result.stops, strict=True)
        ):
            chosen = samples[start:stop, 0]
            chosen = chosen[np.isfinite(chosen)]
            assert (
                result.minimum[i] == chosen.min() and result.maximum[i] == chosen.max()
            )
        assert not result.minimum.flags.writeable and not result.times.flags.writeable
        other = prepare_waveform(
            locator,
            metadata,
            AudioRange(0, 1000),
            1,
            SignalViewSettings(),
            store,
            cpu_bytes=1000,
        )
        assert other.retained_bytes <= 1000 and np.all(other.minimum == 0.5)
    finally:
        store.close()
    assert path.read_bytes() == original


@pytest.mark.parametrize("window", list(AudioWindow))
@pytest.mark.parametrize("hop", [1, 173, 512])
def test_spectrum_matches_scipy_density_and_original_time_axes(
    tmp_path: Path, window: AudioWindow, hop: int
) -> None:
    path = tmp_path / "tone.wav"
    rate = 8000
    samples = np.stack(
        (0.5 * np.sin(2 * np.pi * 1000 * np.arange(67001) / rate), np.ones(67001)),
        axis=1,
    )
    sf.write(path, samples, rate, subtype="DOUBLE")
    dataset = load_media(path).dataset
    locator = locate_audio(dataset, "f", "v", "path", 0, ReferenceSettings(), None)
    metadata = audio_metadata(locator)
    selected = AudioRange(23, 67000)
    settings = SignalViewSettings(
        kind=AudioViewKind.SPECTROGRAM,
        fft=512,
        hop=hop,
        window=window,
        time_bins=16384,
        scale=SpectrumScale.POWER,
    )
    store = ArrayStore()
    try:
        # A short segment provides an independently calculated full-resolution
        # reference; the longer segment crosses decoder block boundaries.
        short = AudioRange(23, 2023)
        exact = prepare_spectrogram(locator, metadata, short, 0, settings, store)
        f, t, complex_values = stft(
            samples[23:2023, 0],
            fs=rate,
            window=get_window(window.scipy_name, 512),
            nperseg=512,
            noverlap=512 - hop,
            nfft=512,
            detrend=False,
            boundary=None,
            padded=False,
            scaling="psd",
        )
        expected = np.abs(complex_values) ** 2
        expected[1:-1] *= 2
        np.testing.assert_allclose(exact.power, expected, rtol=1e-10, atol=1e-15)
        np.testing.assert_allclose(exact.frequencies, f)
        np.testing.assert_allclose(exact.times, t + 23 / rate)
        assert exact.frequency_step == exact.time_step == 1
        assert exact.tail_frames == (2000 - 512) % hop
        assert exact.frequencies[int(exact.power[:, 0].argmax())] == 1000
        long = prepare_spectrogram(
            locator,
            metadata,
            selected,
            0,
            replace(settings, time_bins=5, frequency_bins=10),
            store,
            cpu_bytes=100000,
        )
        assert (
            long.power.shape[0] <= 10 and long.power.shape[1] <= 5 and long.aggregated
        )
        assert long.retained_bytes <= 100000
        for ti in range(long.power.shape[1]):
            first = ti * long.time_step
            expected_time = (
                23
                + 256
                + (first + (min(long.time_step, long.spectral_frames - first) - 1) / 2)
                * hop
            ) / rate
            assert long.times[ti] == pytest.approx(expected_time)
        assert not long.power.flags.writeable and not long.times.flags.writeable
    finally:
        store.close()


def test_nonfinite_short_impulse_padding_cropping_and_decibels(tmp_path: Path) -> None:
    path = tmp_path / "impulse.wav"
    samples = np.zeros((2000, 1))
    samples[1010] = 1
    samples[1020] = np.nan
    samples[1030] = np.inf
    sf.write(path, samples, 8000, subtype="DOUBLE")
    dataset = load_media(path).dataset
    locator = locate_audio(dataset, "f", "", "path", 0, ReferenceSettings(), None)
    metadata = audio_metadata(locator)
    settings = SignalViewSettings(
        kind=AudioViewKind.SPECTROGRAM,
        fft=512,
        hop=512,
        window=AudioWindow.RECTANGULAR,
        frequency_low=1000,
        frequency_high=2000,
    )
    store = ArrayStore()
    try:
        result = prepare_spectrogram(
            locator, metadata, AudioRange(1000, 1100), 0, settings, store
        )
        assert (
            result.window_frames == 100
            and result.nonfinite == 2
            and result.spectral_frames == 1
        )
        assert result.times[0] == 1050 / 8000
        assert result.frequencies.min() == 1000 and result.frequencies.max() == 2000
        np.testing.assert_allclose(result.power, 2 / (8000 * 100))
        np.testing.assert_allclose(result.values, 10 * np.log10(result.power))
        silence = prepare_spectrogram(
            locator, metadata, AudioRange(0, 512), 0, settings, store
        )
        assert np.all(silence.values == settings.db_floor)
        with pytest.raises(ValueError, match="Nyquist"):
            prepare_spectrogram(
                locator,
                metadata,
                AudioRange(),
                0,
                replace(settings, frequency_low=5000, frequency_high=None),
                store,
            )
        stop = Event()
        stop.set()
        with pytest.raises(CancelledError):
            prepare_waveform(
                locator, metadata, AudioRange(), 0, settings, store, stopped=stop.is_set
            )
    finally:
        store.close()


def test_array_extrema_preserve_uint64_and_spectrum_extracts_once(
    tmp_path: Path,
) -> None:
    path = tmp_path / "waves.npz"
    values = np.zeros((2, 70000, 1), dtype=np.uint64)
    values[1, 500] = np.iinfo(np.uint64).max
    np.savez_compressed(path, waves=values)
    before = path.read_bytes()
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping(
        "waves", layout=ArrayLayout.AUDIO, display_axes=(1,), channel_axis=2
    )
    store = ArrayStore(retained_bytes=1, directory=tmp_path)
    try:
        dataset, _ = prepare_array_records(store, catalog, mapping)
        locator = locate_audio(
            dataset, "f", "v", "waves", 1, ReferenceSettings(), None, catalog, mapping
        )
        metadata = audio_metadata(locator, 8000)
        waveform = prepare_waveform(
            locator, metadata, AudioRange(), 0, SignalViewSettings(), store
        )
        assert (
            waveform.maximum.dtype == np.uint64
            and waveform.maximum.astype(np.uint64).max() == np.iinfo(np.uint64).max
        )
        assert store.extractions == 1 and store.stored_bytes == 0
        result = prepare_spectrogram(
            locator,
            metadata,
            AudioRange(),
            0,
            SignalViewSettings(kind=AudioViewKind.SPECTROGRAM),
            store,
        )
        assert (
            store.extractions == 2 and store.stored_bytes == 0 and result.nonfinite == 0
        )
    finally:
        temporary = store.temporary_path
        store.close()
        assert temporary is None or not temporary.exists()
    assert path.read_bytes() == before


def test_selected_array_channel_does_not_require_full_frame_retention(
    tmp_path: Path,
) -> None:
    path = tmp_path / "wide.npy"
    values = np.zeros((1, 8, 262145), dtype=np.float32)
    values[0, :, -1] = np.arange(8)
    np.save(path, values)
    del values
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping(
        "$", layout=ArrayLayout.AUDIO, display_axes=(1,), channel_axis=2
    )
    store = ArrayStore()
    try:
        dataset, _ = prepare_array_records(store, catalog, mapping)
        locator = locate_audio(
            dataset, "f", "v", "$", 0, ReferenceSettings(), None, catalog, mapping
        )
        metadata = audio_metadata(locator, 8000)
        result = prepare_waveform(
            locator,
            metadata,
            AudioRange(),
            262144,
            SignalViewSettings(),
            store,
            cpu_bytes=1024,
        )
        np.testing.assert_array_equal(result.minimum, np.arange(8, dtype=np.float32))
        assert result.retained_bytes <= 1024 and store.temporary_path is None
        spectrum = prepare_spectrogram(
            locator,
            metadata,
            AudioRange(),
            262144,
            SignalViewSettings(kind=AudioViewKind.SPECTROGRAM),
            store,
            cpu_bytes=100000,
        )
        assert spectrum.window_frames == 8 and np.isfinite(spectrum.power).all()
    finally:
        store.close()


@pytest.mark.parametrize(
    "settings",
    [
        SignalViewSettings(fft=17),
        SignalViewSettings(hop=0),
        SignalViewSettings(hop=2048),
        SignalViewSettings(frequency_low=float("nan")),
        SignalViewSettings(frequency_high=0),
        SignalViewSettings(db_floor=1),
        SignalViewSettings(time_bins=0),
        SignalViewSettings(waveform_bins=0),
    ],
)
def test_invalid_signal_controls_have_diagnostics(settings: SignalViewSettings) -> None:
    with pytest.raises(ValueError):
        settings.validate()
