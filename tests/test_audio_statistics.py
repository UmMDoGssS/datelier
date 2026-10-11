"""Known signals, finite-value denominators, thresholds and bounded scan invariants."""

from concurrent.futures import CancelledError
from pathlib import Path
from threading import Event

import numpy as np
import pytest
import soundfile as sf

from datelier.inspection.arrays.mapping import ArrayLayout, ArrayRecordMapping
from datelier.inspection.audio.profile_types import AudioProgress, AudioThresholds
from datelier.inspection.audio.sources import audio_metadata, locate_audio
from datelier.inspection.audio.statistics import profile_signal
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays import ArrayStore
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.records import prepare_array_records
from datelier.io.media import load_media


@pytest.mark.parametrize("block_frames", [1, 2, 3, 7, 65536])
def test_finite_channel_rms_clipping_and_all_channel_silence(
    tmp_path: Path, block_frames: int
) -> None:
    path = tmp_path / "signal.wav"
    samples = np.array(
        [
            [0, 0],
            [0, 0],
            [0.5, 0.5],
            [-0.5, 0],
            [1, 0],
            [-1, -1],
            [np.nan, 0],
            [np.inf, 0],
        ]
    )
    sf.write(path, samples, 8000, subtype="DOUBLE")
    before = path.read_bytes()
    dataset = load_media(path).dataset
    locator = locate_audio(
        dataset, "file", "records", "path", 0, ReferenceSettings(), None
    )
    metadata = audio_metadata(locator)
    store, progress = ArrayStore(), AudioProgress()
    try:
        profile = profile_signal(
            locator,
            metadata,
            AudioRange(),
            AudioThresholds(),
            store,
            progress=progress,
            block_frames=block_frames,
        )
        left, right = profile.channels
        assert (left.samples, left.finite, left.nonfinite) == (8, 6, 2)
        assert (left.minimum, left.maximum, left.peak) == ("-1.0", "1.0", "1.0")
        assert left.mean == 0 and left.rms == pytest.approx((2.5 / 6) ** 0.5)
        assert (left.clipped, left.silent) == (2, 2)
        assert right.rms == pytest.approx((1.25 / 8) ** 0.5)
        assert (right.finite, right.clipped, right.silent) == (8, 1, 6)
        assert (
            profile.silent_frames,
            profile.longest_silence_frames,
            profile.nonfinite_frames,
        ) == (2, 2, 2)
        assert profile.duration == 8 / 8000 and profile.silence_duration == 2 / 8000
        assert progress.value == (8, 8)
        changed = profile_signal(
            locator,
            metadata,
            AudioRange(2, 6),
            AudioThresholds(clipping=0.5, silence=0.5),
            store,
            block_frames=block_frames,
        )
        assert changed.channels[0].clipped == 4 and changed.channels[0].silent == 2
        assert changed.silent_frames == changed.longest_silence_frames == 2
        assert changed.range == AudioRange(2, 6) and changed.frames == 4
    finally:
        store.close()
    assert path.read_bytes() == before


def test_pcm_rails_and_empty_signal(tmp_path: Path) -> None:
    path = tmp_path / "signal.wav"
    sf.write(path, np.array([-1, 1, 0.25, 0]), 44100, subtype="PCM_16")
    dataset = load_media(path).dataset
    locator = locate_audio(dataset, "f", "", "path", 0, ReferenceSettings(), None)
    metadata = audio_metadata(locator)
    store = ArrayStore()
    try:
        profile = profile_signal(
            locator, metadata, AudioRange(), AudioThresholds(), store
        )
        assert profile.clipping_bounds == (-1, 32767 / 32768)
        assert profile.channels[0].clipped == 2 and profile.channels[0].silent == 1
        empty = profile_signal(
            locator, metadata, AudioRange(1, 1), AudioThresholds(), store
        )
        assert empty.frames == 0 and empty.duration == 0 and empty.silent_frames == 0
        assert empty.channels[0].rms is empty.channels[0].minimum is None
    finally:
        store.close()


def test_nonfinite_samples_do_not_count_as_silence_or_clip(tmp_path: Path) -> None:
    path = tmp_path / "nonfinite.wav"
    sf.write(path, np.array([np.nan, np.inf, -np.inf]), 8000, subtype="DOUBLE")
    dataset = load_media(path).dataset
    locator = locate_audio(dataset, "f", "", "path", 0, ReferenceSettings(), None)
    store = ArrayStore()
    try:
        profile = profile_signal(
            locator, audio_metadata(locator), AudioRange(), AudioThresholds(), store
        )
        channel = profile.channels[0]
        assert (channel.samples, channel.finite, channel.nonfinite) == (3, 0, 3)
        assert channel.mean is channel.rms is channel.minimum is channel.peak is None
        assert channel.clipped == channel.silent == profile.silent_frames == 0
        assert profile.nonfinite_frames == 3
    finally:
        store.close()


@pytest.mark.parametrize("dtype", ["i2", "u8", "f8", "f16"])
def test_original_array_units_extrema_and_stable_huge_rms(
    tmp_path: Path, dtype: str
) -> None:
    path = tmp_path / "waves.npz"
    dt = np.dtype(dtype)
    if dt.kind in "iu":
        bounds = np.iinfo(dtype)
        values = np.array([[bounds.min, 0, bounds.max]], dtype=dtype)
    else:
        values = np.array([[-1e300, 0, 1e300]], dtype=dtype)
    np.savez_compressed(path, waves=values)
    before = path.read_bytes()
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping("waves", layout=ArrayLayout.AUDIO, display_axes=(1,))
    store = ArrayStore(retained_bytes=1, directory=tmp_path)
    try:
        dataset, _ = prepare_array_records(store, catalog, mapping)
        locator = locate_audio(
            dataset,
            "file",
            "waves",
            "waves",
            0,
            ReferenceSettings(),
            None,
            catalog,
            mapping,
        )
        unknown = audio_metadata(locator)
        with pytest.raises(ValueError, match="Configure.*sample rate"):
            profile_signal(locator, unknown, AudioRange(), AudioThresholds(), store)
        metadata = audio_metadata(locator, 48000)
        profile = profile_signal(
            locator, metadata, AudioRange(), AudioThresholds(), store, block_frames=1
        )
        channel = profile.channels[0]
        assert (channel.minimum, channel.maximum) == (
            str(values.min()),
            str(values.max()),
        )
        expected = float(
            np.sqrt(
                np.mean(
                    (
                        values.astype(np.longdouble)
                        / np.max(np.abs(values.astype(np.longdouble)))
                    )
                    ** 2
                )
            )
            * np.max(np.abs(values.astype(np.longdouble)))
        )
        assert (
            channel.rms == pytest.approx(expected)
            and channel.rms is not None
            and np.isfinite(channel.rms)
        )
        assert channel.clipped == (3 if dtype == "u8" else 2)
        assert store.extractions == 1 and store.stored_bytes == 0
    finally:
        temporary = store.temporary_path
        store.close()
        assert temporary is None or not temporary.exists()
    assert path.read_bytes() == before


def test_long_silence_runs_survive_block_boundaries(tmp_path: Path) -> None:
    path = tmp_path / "silence.wav"
    values = np.zeros((1200, 2))
    values[0, 0] = values[1100, 0] = 0.5
    values[900, 1] = 0.5
    sf.write(path, values, 16000, subtype="DOUBLE")
    dataset = load_media(path).dataset
    locator = locate_audio(dataset, "f", "v", "path", 0, ReferenceSettings(), None)
    store = ArrayStore()
    try:
        profile = profile_signal(
            locator,
            audio_metadata(locator),
            AudioRange(),
            AudioThresholds(),
            store,
            block_frames=31,
        )
        assert profile.silent_frames == 1197 and profile.longest_silence_frames == 899
        stop = Event()
        stop.set()
        with pytest.raises(CancelledError):
            profile_signal(
                locator,
                audio_metadata(locator),
                AudioRange(),
                AudioThresholds(),
                store,
                stopped=stop.is_set,
            )
        for thresholds in (
            AudioThresholds(0),
            AudioThresholds(float("nan")),
            AudioThresholds(silence=-1),
            AudioThresholds(silence=float("inf")),
        ):
            with pytest.raises(ValueError):
                profile_signal(
                    locator, audio_metadata(locator), AudioRange(), thresholds, store
                )
    finally:
        store.close()
