"""Analytical HTK triangles and independent dense PSD integration references."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from scipy.signal import get_window, stft

from datelier.inspection.audio.decoding import audio_metadata, locate_audio
from datelier.inspection.audio.signal import (
    AudioViewKind,
    SignalViewSettings,
    SpectrumScale,
)
from datelier.inspection.audio.signal.mel import hz_to_mel, mel_filters, mel_to_hz
from datelier.inspection.audio.signal.spectra import prepare_spectrogram
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.references import ReferenceSettings
from datelier.io.arrays import ArrayStore
from datelier.io.media import load_media


def test_analytical_geometric_edges_triangles_and_band_integration() -> None:
    # Equal mel intervals give these independently chosen geometric Hz edges.
    bank = mel_filters(22400, 32, 3, 0, 10500)
    np.testing.assert_allclose(bank.edges, [0, 700, 2100, 4900, 10500], atol=1e-10)
    np.testing.assert_allclose(bank.centers, [700, 2100, 4900], atol=1e-10)
    np.testing.assert_allclose(bank.apply(np.ones(17)), [1050, 2100, 4200])
    chosen = bank.weights[bank.bands == 0]
    np.testing.assert_allclose(chosen[chosen > 1e-12], [1, 0.5])
    density = np.zeros(17)
    density[3] = 2
    np.testing.assert_allclose(bank.apply(density), [0, 1400, 0], atol=1e-10)
    assert bank.empty == 0 and len(bank.weights) <= 2 * 17
    assert hz_to_mel(1000) == pytest.approx(999.9855371396244)
    assert mel_to_hz(hz_to_mel(2000)) == pytest.approx(2000)


@pytest.mark.parametrize(
    "rate,fft,bands", [(8000, 64, 1), (22050, 512, 8), (8000, 512, 64), (8000, 64, 512)]
)
def test_mel_power_matches_independent_dense_scipy_reference(
    tmp_path: Path, rate: int, fft: int, bands: int
) -> None:
    path = tmp_path / "tone.wav"
    signal = 0.5 * np.sin(2 * np.pi * 1000 * np.arange(3000) / rate)
    sf.write(path, signal, rate, subtype="DOUBLE")
    original = path.read_bytes()
    dataset = load_media(path).dataset
    locator = locate_audio(dataset, "f", "v", "path", 0, ReferenceSettings(), None)
    settings = SignalViewSettings(
        mode=AudioViewKind.MEL,
        fft=fft,
        hop=fft // 2,
        mel_bands=bands,
        frequency_low=128,
        frequency_high=rate / 2,
        frequency_bins=1,
        scale=SpectrumScale.POWER,
    )
    store = ArrayStore()
    try:
        result = prepare_spectrogram(
            locator, audio_metadata(locator), AudioRange(17, 2917), 0, settings, store
        )
        frequencies, times, complex_values = stft(
            signal[17:2917],
            fs=rate,
            window=get_window("hann", fft),
            nperseg=fft,
            noverlap=fft // 2,
            nfft=fft,
            boundary=None,
            padded=False,
            detrend=False,
            scaling="psd",
        )
        density = np.abs(complex_values) ** 2
        density[1:-1] *= 2
        edges = 700 * (
            10
            ** (
                np.linspace(
                    2595 * np.log10(1 + 128 / 700),
                    2595 * np.log10(1 + rate / 1400),
                    bands + 2,
                )
                / 2595
            )
            - 1
        )
        dense = np.zeros((bands, len(frequencies)))
        for i in range(bands):
            first, center, last = edges[i : i + 3]
            dense[i] = np.maximum(
                0,
                np.minimum(
                    (frequencies - first) / (center - first),
                    (last - frequencies) / (last - center),
                ),
            )
        expected = dense @ density * rate / fft
        np.testing.assert_allclose(result.power, expected, rtol=1e-10, atol=1e-13)
        np.testing.assert_allclose(result.frequencies, edges[1:-1])
        np.testing.assert_allclose(result.times, times + 17 / rate)
        assert result.frequency_step == result.time_step == 1
        assert result.mel_empty_bands == np.count_nonzero(
            ~np.any(dense > 1e-12, axis=1)
        )
        converted = prepare_spectrogram(
            locator,
            audio_metadata(locator),
            AudioRange(17, 2917),
            0,
            replace(settings, scale=SpectrumScale.DECIBELS, time_bins=3),
            store,
        )
        assert converted.power.shape[1] <= 3 and converted.power.shape[0] == bands
        for column in range(converted.power.shape[1]):
            start = column * converted.time_step
            np.testing.assert_allclose(
                converted.power[:, column],
                expected[:, start : start + converted.time_step].max(axis=1),
                rtol=1e-10,
                atol=1e-13,
            )
        np.testing.assert_allclose(
            converted.values,
            np.maximum(10 * np.log10(np.maximum(converted.power, 1e-12)), -120),
        )
        assert path.read_bytes() == original
    finally:
        store.close()


def test_empty_mel_bands_are_retained_and_large_bank_stays_sparse(
    tmp_path: Path,
) -> None:
    bank = mel_filters(48000, 65536, 512, 0, 24000)
    assert len(bank.weights) <= 2 * (65536 // 2 + 1)
    assert bank.weights.nbytes + bank.bins.nbytes + bank.bands.nbytes < 2 * 1024**2
    path = tmp_path / "silence.wav"
    sf.write(path, np.zeros(100), 8000, subtype="DOUBLE")
    dataset = load_media(path).dataset
    locator = locate_audio(dataset, "f", "v", "path", 0, ReferenceSettings(), None)
    store = ArrayStore()
    try:
        result = prepare_spectrogram(
            locator,
            audio_metadata(locator),
            AudioRange(),
            0,
            SignalViewSettings(
                mode=AudioViewKind.MEL,
                fft=16,
                hop=16,
                mel_bands=512,
                frequency_low=1001,
                frequency_high=1002,
            ),
            store,
        )
        assert result.mel_empty_bands == 512
        assert np.all(result.power == 0) and np.all(result.values == -120)
        assert result.power.shape[0] == 512 and result.retained_bytes <= 16 * 1024**2
    finally:
        store.close()
