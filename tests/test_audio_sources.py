"""Header-first signal loading, exact samples and original record provenance."""

from concurrent.futures import CancelledError
from dataclasses import replace
from pathlib import Path
from threading import Event
from unittest.mock import patch

import numpy as np
import polars as pl
import pytest
import soundfile as sf

from datelier.core.dataset import Dataset, SourceReference
from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
)
from datelier.inspection.audio.reading import audio_blocks, prepare_window
from datelier.inspection.audio.sources import audio_metadata, locate_audio
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.references.types import ReferenceMapping, ReferenceSettings
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.records import prepare_array_records
from datelier.io.arrays.storage import ArrayStore


def dataset(root: Path, paths: list[str | None]) -> Dataset:
    path = root / "source.csv"
    path.write_text("audio\n")
    stat = path.stat()
    return Dataset.from_source(
        pl.DataFrame({"audio": paths}, schema_overrides={"audio": pl.String}),
        SourceReference(path, stat.st_size, stat.st_mtime_ns),
    )


@pytest.mark.parametrize("rate,channels", [(8000, 1), (22050, 2), (48000, 4)])
def test_headers_do_not_read_payload_and_file_rate_is_preserved(
    tmp_path: Path, rate: int, channels: int
) -> None:
    path = tmp_path / "signal.wav"
    values = np.linspace(-1, 1, 101 * channels).reshape(101, channels)
    sf.write(path, values, rate, subtype="DOUBLE")
    before = path.read_bytes()
    table = dataset(tmp_path, [path.name])
    locator = locate_audio(
        table, "file", "records", "audio", 0, ReferenceSettings(), None
    )
    with patch.object(sf.SoundFile, "read", side_effect=AssertionError("payload read")):
        metadata = audio_metadata(locator, 44100)
    assert (metadata.frames, metadata.channels, metadata.sample_rate) == (
        101,
        channels,
        rate,
    )
    assert metadata.duration == 101 / rate and metadata.require_rate() == rate
    assert (
        metadata.units == "full-scale amplitude"
        and "no resampling" in metadata.description
    )
    store = ArrayStore()
    try:
        prepared = prepare_window(locator, metadata, AudioRange(7, 84), store)
        np.testing.assert_array_equal(prepared.raw, values[7:84])
        assert (
            not prepared.raw.flags.writeable
            and prepared.retained_bytes == 77 * channels * 8
        )
        with audio_blocks(
            locator, metadata, store, block_frames=9, block_bytes=channels * 8 * 3
        ) as blocks:
            copied = list(blocks)
        assert [block.start for block in copied] == list(range(0, 101, 3))
        assert all(block.samples.nbytes <= channels * 8 * 3 for block in copied)
        np.testing.assert_array_equal(
            np.concatenate([b.samples for b in copied]), values
        )
        assert store.temporary_path is None
    finally:
        store.close()
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "format,subtype", [("WAV", "PCM_16"), ("FLAC", "PCM_16"), ("OGG", "VORBIS")]
)
def test_common_codecs_decode_known_signals(
    tmp_path: Path, format: str, subtype: str
) -> None:
    path = tmp_path / ("tone." + format.lower())
    values = 0.25 * np.sin(2 * np.pi * 440 * np.arange(24000) / 24000)
    sf.write(path, values, 24000, format=format, subtype=subtype)
    table = dataset(tmp_path, [path.name])
    locator = locate_audio(table, "file", "", "audio", 0, ReferenceSettings(), None)
    metadata = audio_metadata(locator)
    store = ArrayStore()
    try:
        prepared = prepare_window(locator, metadata, AudioRange(0, 24000), store)
        assert metadata.format == format and metadata.channels == 1
        assert prepared.raw.shape == (24000, 1)
        assert float(np.sqrt(np.square(prepared.raw).mean())) == pytest.approx(
            0.25 / 2**0.5, abs=0.002
        )
    finally:
        store.close()


def test_diagnostics_and_explicit_duplicate_stem_mapping(tmp_path: Path) -> None:
    path = tmp_path / "bad.m4a"
    path.write_bytes(b"unsupported or corrupt")
    table = dataset(tmp_path, [None, "missing.wav", path.name, "tone"])
    with pytest.raises(ValueError, match="nonempty"):
        locate_audio(table, "a", "", "audio", 0, ReferenceSettings(), None)
    with pytest.raises(ValueError):
        locate_audio(table, "a", "", "audio", 1, ReferenceSettings(), None)
    locator = locate_audio(table, "a", "", "audio", 2, ReferenceSettings(), None)
    with pytest.raises(ValueError, match="Cannot decode audio header"):
        audio_metadata(locator)
    for name in ("a", "b"):
        folder = tmp_path / name
        folder.mkdir()
        sf.write(folder / "tone.wav", np.zeros(20), 8000)
    settings = ReferenceSettings(
        mappings=(ReferenceMapping("audio", "tone", str(tmp_path / "b" / "tone.wav")),)
    )
    chosen = locate_audio(table, "a", "", "audio", 3, settings, None)
    assert chosen.asset is not None and chosen.asset.path == tmp_path / "b" / "tone.wav"
    assert table.table.get_column("audio")[3] == "tone"


@pytest.mark.parametrize("order", [(0, 1, 2), (2, 0, 1), (1, 2, 0)])
@pytest.mark.parametrize("compressed", [False, True])
def test_array_channels_axes_rates_and_source_rows(
    tmp_path: Path, order: tuple[int, ...], compressed: bool
) -> None:
    path = tmp_path / "signals.npz"
    values = np.arange(3 * 17 * 2, dtype=">i2").reshape(3, 17, 2)
    (np.savez_compressed if compressed else np.savez)(
        path, waves=values.transpose(order), label=np.array([9, 2, 5])
    )
    before = path.read_bytes()
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping(
        "waves",
        order.index(0),
        ArrayLayout.AUDIO,
        (order.index(1),),
        order.index(2),
        supporting=(SupportingArray("label", "label"),),
    )
    store = ArrayStore(retained_bytes=1, directory=tmp_path)
    try:
        table, _ = prepare_array_records(store, catalog, mapping)
        sorted_table = table.table.sort("label")
        table = table.with_rows(sorted_table, table.row_ids.gather([1, 2, 0]))
        locator = locate_audio(
            table,
            "arrays",
            "waves",
            "waves",
            0,
            ReferenceSettings(),
            None,
            catalog,
            mapping,
        )
        assert locator.source_index == locator.origin.row_id == 1
        with patch.object(
            store, "open_member", side_effect=AssertionError("payload read")
        ):
            missing = audio_metadata(locator)
            metadata = audio_metadata(locator, 16000)
        assert missing.duration is None and missing.sample_rate is None
        with pytest.raises(ValueError, match="Configure.*sample rate"):
            missing.require_rate()
        assert (metadata.frames, metadata.channels, metadata.duration) == (
            17,
            2,
            17 / 16000,
        )
        assert metadata.dtype == values.dtype
        assert metadata.units == "array units"
        prepared = prepare_window(locator, metadata, AudioRange(4, 13), store)
        np.testing.assert_array_equal(prepared.raw, values[1, 4:13])
        with audio_blocks(
            locator, metadata, store, AudioRange(4, 13), block_bytes=6, channel=1
        ) as blocks:
            chosen = list(blocks)
        assert all(
            block.samples.shape[1] == 1 and block.samples.nbytes <= 6
            for block in chosen
        )
        np.testing.assert_array_equal(
            np.concatenate([block.samples[:, 0] for block in chosen]),
            values[1, 4:13, 1],
        )
        assert prepared.raw.dtype == metadata.dtype
        assert store.stored_bytes == 0  # Oversized extraction released after its lease.
        assert table.table.get_column("label")[0] == 2
    finally:
        temporary = store.temporary_path
        store.close()
        assert temporary is None or not temporary.exists()
    assert path.read_bytes() == before


def test_integer_pcm_float_nonfinite_and_empty_samples_preserved(
    tmp_path: Path,
) -> None:
    path = tmp_path / "waves.npy"
    values = np.array([[0.0, np.nan, np.inf, -np.inf, 1.5]], dtype=np.float32)
    np.save(path, values)
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping("$", layout=ArrayLayout.AUDIO, display_axes=(1,))
    store = ArrayStore()
    try:
        table, _ = prepare_array_records(store, catalog, mapping)
        locator = locate_audio(
            table, "f", "v", "$", 0, ReferenceSettings(), None, catalog, mapping
        )
        metadata = audio_metadata(locator, 12345)
        prepared = prepare_window(locator, metadata, AudioRange(), store)
        np.testing.assert_array_equal(prepared.raw[:, 0], values[0])
        assert prepared.raw.dtype == np.float32
        empty = prepare_window(locator, metadata, AudioRange(2, 2), store)
        assert empty.raw.shape == (0, 1)
        with pytest.raises(ValueError, match="CPU budget"):
            prepare_window(locator, metadata, AudioRange(), store, cpu_bytes=4)
        for selected in (AudioRange(-1, 2), AudioRange(3, 1), AudioRange(0, 6)):
            with pytest.raises(ValueError):
                prepare_window(locator, metadata, selected, store)
        with pytest.raises(ValueError, match="sample rate"):
            audio_metadata(locator, 0)
        with pytest.raises(ValueError, match="one complete sample frame"):
            with audio_blocks(locator, metadata, store, block_bytes=1):
                pass
    finally:
        store.close()


def test_asset_change_cancellation_and_mismatched_metadata_release(
    tmp_path: Path,
) -> None:
    path = tmp_path / "signal.wav"
    sf.write(path, np.arange(100, dtype=np.float64), 8000, subtype="DOUBLE")
    table = dataset(tmp_path, [path.name])
    locator = locate_audio(table, "a", "", "audio", 0, ReferenceSettings(), None)
    metadata = audio_metadata(locator)
    stop = Event()
    store = ArrayStore()
    try:
        with pytest.raises(CancelledError):
            with audio_blocks(
                locator, metadata, store, block_frames=10, stopped=stop.is_set
            ) as blocks:
                assert next(blocks).start == 0
                stop.set()
                next(blocks)
        with pytest.raises(ValueError, match="metadata changed"):
            prepare_window(
                locator, replace(metadata, frames=99), AudioRange(0, 1), store
            )
        with pytest.raises(ValueError, match="asset changed"):
            with audio_blocks(locator, metadata, store, block_frames=10) as blocks:
                next(blocks)
                path.write_bytes(b"changed")
                next(blocks)
    finally:
        store.close()


def test_abandoned_array_lease_releases_oversized_payload(tmp_path: Path) -> None:
    path = tmp_path / "waves.npz"
    np.savez_compressed(path, waves=np.ones((2, 1000)))
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping("waves", layout=ArrayLayout.AUDIO, display_axes=(1,))
    store = ArrayStore(retained_bytes=1, directory=tmp_path)
    table, _ = prepare_array_records(store, catalog, mapping)
    locator = locate_audio(
        table, "a", "v", "waves", 0, ReferenceSettings(), None, catalog, mapping
    )
    metadata = audio_metadata(locator, 16000)
    with pytest.raises(CancelledError):
        with audio_blocks(locator, metadata, store, block_frames=10) as blocks:
            copied = next(blocks)
            temporary = store.temporary_path
            assert store.stored_bytes > store.limit
            store.abandon()
    assert store.stored_bytes == 0 and temporary is not None and not temporary.exists()
    np.testing.assert_array_equal(copied.samples, np.ones((10, 1)))
    store.close()


@pytest.mark.parametrize("shape,dtype", [((2, 3, 0), "f4"), ((2, 3, 1), "c8")])
def test_invalid_waveform_arrays_have_diagnostics(
    tmp_path: Path, shape: tuple[int, ...], dtype: str
) -> None:
    path = tmp_path / "waves.npy"
    np.save(path, np.zeros(shape, dtype=dtype))
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping(
        "$", layout=ArrayLayout.AUDIO, display_axes=(1,), channel_axis=2
    )
    store = ArrayStore()
    try:
        table, _ = prepare_array_records(store, catalog, mapping)
        locator = locate_audio(
            table, "a", "v", "$", 0, ReferenceSettings(), None, catalog, mapping
        )
        with pytest.raises(ValueError, match="empty channel|real numeric"):
            audio_metadata(locator, 16000)
    finally:
        store.close()
