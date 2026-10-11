"""Signal controls invalidate relevant work and never publish across closed records."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch

import numpy as np
import soundfile as sf

from datelier.inspection.audio.decoding import prepare_metadata
from datelier.inspection.audio.signal import (
    AudioViewKind,
    SignalViewSettings,
    SpectralView,
    SpectrumScale,
    WaveformEnvelope,
)
from datelier.inspection.audio.signal.jobs import SignalViewJobs
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.heatmaps import Colormap
from datelier.inspection.references import ReferenceSettings
from datelier.io.arrays import ArrayStore
from datelier.io.media import load_media


def wait(jobs: SignalViewJobs) -> None:
    deadline = monotonic() + 5
    while jobs.busy and monotonic() < deadline:
        jobs.poll()
        sleep(0.001)
    assert not jobs.busy


def gated[**P, T](
    function: Callable[P, T], entered: Event, release: Event
) -> Callable[P, T]:
    def delayed(*args: P.args, **kwargs: P.kwargs) -> T:
        entered.set()
        assert release.wait(5)
        return function(*args, **kwargs)

    return delayed


def test_waveform_relevance_and_spectral_scale_reuses_prepared_power(
    tmp_path: Path,
) -> None:
    path = tmp_path / "tone.wav"
    sf.write(path, np.ones((2000, 2)), 8000, subtype="DOUBLE")
    dataset = load_media(path).dataset
    source = prepare_metadata(
        dataset, "a", "records", "path", 0, ReferenceSettings(), None
    )
    jobs, arrays = SignalViewJobs(), ArrayStore()
    try:
        jobs.bind(source)
        settings = SignalViewSettings()
        selected = AudioRange(0, 2000)
        jobs.request(selected, 0, settings, arrays, 1024 * 1024)
        wait(jobs)
        waveform = jobs.active
        assert isinstance(waveform, WaveformEnvelope)
        jobs.request(
            selected,
            0,
            replace(settings, fft=2048, frequency_high=1000),
            arrays,
            1024 * 1024,
        )
        assert not jobs.busy and jobs.active is waveform
        spectral = replace(settings, mode=AudioViewKind.SPECTROGRAM)
        jobs.request(selected, 1, spectral, arrays, 1024 * 1024)
        wait(jobs)
        assert isinstance(jobs.active, SpectralView)
        power = jobs.active.power
        with patch(
            "datelier.inspection.audio.signal.jobs.prepare_spectrogram",
            side_effect=AssertionError("must reuse PSD"),
        ):
            jobs.request(
                selected,
                1,
                replace(spectral, scale=SpectrumScale.POWER),
                arrays,
                1024 * 1024,
            )
            wait(jobs)
        assert isinstance(jobs.active, SpectralView) and jobs.active.power is power
        assert jobs.active.values is power
        with patch(
            "datelier.inspection.audio.signal.jobs.prepare_spectrogram",
            side_effect=AssertionError("color controls must reuse PSD"),
        ):
            jobs.request(
                selected,
                1,
                replace(
                    spectral,
                    scale=SpectrumScale.POWER,
                    colormap=Colormap.PURPLE_GOLD,
                    color_range=(0, 1),
                ),
                arrays,
                1024**2,
            )
            wait(jobs)
        assert isinstance(jobs.active, SpectralView) and jobs.active.power is power
        assert jobs.active.color_bounds == (0, 1) and all(
            not tile.rgba.flags.writeable for tile in jobs.active.tiles
        )
        spectral = replace(spectral, colormap=Colormap.PURPLE_GOLD, color_range=(0, 1))
        jobs.request(
            selected,
            1,
            replace(spectral, scale=SpectrumScale.POWER, db_floor=-50),
            arrays,
            1024 * 1024,
        )
        assert not jobs.busy
        jobs.request(selected, 0, spectral, arrays, 1024 * 1024)
        assert jobs.active is None
        wait(jobs)
        assert jobs.active is not None and jobs.active.channel == 0
    finally:
        jobs.close()
        arrays.close()


def test_running_view_closure_discards_results_and_releases_source(
    tmp_path: Path,
) -> None:
    path = tmp_path / "tone.wav"
    sf.write(path, np.zeros(10000), 8000)
    dataset = load_media(path).dataset
    source = prepare_metadata(
        dataset, "a", "records", "path", 0, ReferenceSettings(), None
    )
    entered, release = Event(), Event()
    arrays = ArrayStore()
    with ThreadPoolExecutor(max_workers=1) as pool:
        jobs = SignalViewJobs(pool)
        try:
            jobs.bind(source)
            with patch.object(
                sf.SoundFile, "read", gated(sf.SoundFile.read, entered, release)
            ):
                jobs.request(AudioRange(), 0, SignalViewSettings(), arrays, 1024 * 1024)
                assert entered.wait(5)
                jobs.bind(
                    (
                        replace(
                            source[0], origin=replace(source[0].origin, file_id="b")
                        ),
                        source[1],
                    )
                )
                assert jobs.active is None and not jobs.busy
                jobs.close()
                release.set()
                pool.shutdown(wait=True)
            jobs.poll()
            assert jobs.active is None
            jobs.request(AudioRange(), 0, SignalViewSettings(), arrays, 1024 * 1024)
            assert not jobs.busy
        finally:
            release.set()
            jobs.close()
            arrays.close()


def test_mel_relevance_display_reuse_and_band_changes(tmp_path: Path) -> None:
    path = tmp_path / "tone.wav"
    sf.write(path, np.ones(4000), 8000, subtype="DOUBLE")
    source = prepare_metadata(
        load_media(path).dataset, "a", "records", "path", 0, ReferenceSettings(), None
    )
    jobs, arrays = SignalViewJobs(), ArrayStore()
    settings = SignalViewSettings(mode=AudioViewKind.MEL, mel_bands=32)
    selected = AudioRange(0, 4000)
    try:
        jobs.bind(source)
        jobs.request(selected, 0, settings, arrays, 1024**2)
        wait(jobs)
        previous = jobs.active
        assert isinstance(previous, SpectralView) and previous.power.shape[0] == 32
        jobs.request(
            selected,
            0,
            replace(settings, frequency_bins=1, waveform_bins=16),
            arrays,
            1024**2,
        )
        assert not jobs.busy and jobs.active is previous
        with patch(
            "datelier.inspection.audio.signal.jobs.prepare_spectrogram",
            side_effect=AssertionError("must reuse band power"),
        ):
            jobs.request(
                selected,
                0,
                replace(
                    settings, scale=SpectrumScale.POWER, colormap=Colormap.PURPLE_GOLD
                ),
                arrays,
                1024**2,
            )
            wait(jobs)
        assert (
            isinstance(jobs.active, SpectralView)
            and jobs.active.power is previous.power
        )
        jobs.request(selected, 0, replace(settings, mel_bands=16), arrays, 1024**2)
        assert jobs.active is None
        wait(jobs)
        assert (
            isinstance(jobs.active, SpectralView) and jobs.active.power.shape[0] == 16
        )
        spectral = replace(settings, mode=AudioViewKind.SPECTROGRAM)
        jobs.request(selected, 0, spectral, arrays, 1024**2)
        wait(jobs)
        previous = jobs.active
        jobs.request(selected, 0, replace(spectral, mel_bands=16), arrays, 1024**2)
        assert not jobs.busy and jobs.active is previous
    finally:
        jobs.close()
        arrays.close()
