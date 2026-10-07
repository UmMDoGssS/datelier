"""Header-only laziness, exact scalar statistics, scope identity and array leases."""

from dataclasses import replace
from pathlib import Path
from threading import Event

import numpy as np
import polars as pl
import pytest
import soundfile as sf
from audio_comparison_fixtures import fixture

from datelier.core.dataset import Dataset
from datelier.inspection.arrays.mapping import ArrayLayout, ArrayRecordMapping
from datelier.inspection.audio.collections.scan import audio_positions, scan_collection
from datelier.inspection.audio.collections.settings import (
    AudioCollectionSettings,
    AudioProfileMode,
    AudioScope,
    AudioScopeMode,
)
from datelier.inspection.audio.collections.types import (
    AudioCollectionProfile,
    CollectionProgress,
)
from datelier.inspection.audio.comparisons.types import AudioComparisonInput
from datelier.inspection.audio.profile_types import AudioThresholds
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.storage import ArrayStore


def scan(item: AudioComparisonInput, arrays: ArrayStore) -> AudioCollectionProfile:
    return scan_collection(
        item.dataset,
        item.source.file_id,
        item.view_name,
        item.source.profile,
        item.selection,
        item.references,
        item.index,
        arrays,
        Event(),
        CollectionProgress(),
        item.catalog,
        item.mapping,
    )[0]


def test_header_only_reads_no_samples_and_retains_failure_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs, _ = fixture(tmp_path, AudioProfileMode.HEADERS)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Header-only commands must not decode samples")

    monkeypatch.setattr("soundfile.SoundFile.read", forbidden)
    store = ArrayStore(retained_bytes=0)
    try:
        profile = scan(inputs[1], store)
        assert profile.records["status"].to_list() == [
            "Ready",
            "Ready",
            "Null",
            "Failed",
            "Failed",
        ]
        assert profile.records["duration"].to_list() == [1, 2, None, None, None]
        assert profile.channel_records.is_empty()
        assert profile.records["silence_fraction"].null_count() == 5
        assert store.extractions == 0 and store.temporary_path is None
        assert "missing" in profile.records["diagnostic"][3].lower()
    finally:
        store.close()


def test_exact_known_records_use_finite_denominators_and_original_thresholds(
    tmp_path: Path,
) -> None:
    inputs, _ = fixture(tmp_path)
    store = ArrayStore(retained_bytes=0)
    try:
        profile = scan(inputs[0], store)
        assert profile.records["duration"].to_list() == [1, 2]
        assert profile.channel_records["rms"].to_list() == [0.25, 0.25, 0.5, 0.5]
        assert profile.channel_records["mean"].to_list() == [0.25, -0.25, 0.5, -0.5]
        assert profile.records["silence_fraction"].to_list() == [0, 0]
        assert profile.file_id == "train" and profile.view_name == "records"
        assert profile.revision == inputs[0].dataset.revision
        changed = replace(
            inputs[0],
            source=replace(
                inputs[0].source,
                profile=replace(
                    inputs[0].source.profile, thresholds=AudioThresholds(0.5, 0.25)
                ),
            ),
        )
        alternate = scan(changed, store)
        assert alternate.channel_records["clipped_fraction"].to_list() == [0, 0, 1, 1]
        assert alternate.records["silence_fraction"].to_list() == [1, 0]
        assert alternate.channel_records["clipping_high"].to_list() == ["0.5"] * 4
        assert scan(inputs[1], store).records["longest_silence"].to_list()[:2] == [1, 0]
    finally:
        store.close()


def test_scopes_preserve_original_ids_through_sorting(tmp_path: Path) -> None:
    inputs, _ = fixture(tmp_path)
    original = inputs[1].dataset
    reversed_data = original.with_rows(
        original.table.reverse(), original.row_ids.reverse()
    )
    settings = AudioCollectionSettings(
        "audio", scope=AudioScope(AudioScopeMode.RANDOM, count=3, seed=9)
    )
    first = original.row_ids.gather(audio_positions(original, settings, ()))
    second = reversed_data.row_ids.gather(audio_positions(reversed_data, settings, ()))
    assert set(first.to_list()) == set(second.to_list())
    selected = replace(settings, scope=AudioScope(AudioScopeMode.SELECTION))
    assert reversed_data.row_ids.gather(
        audio_positions(reversed_data, selected, (0, 3))
    ).to_list() == [3, 0]
    ranged = replace(settings, scope=AudioScope(AudioScopeMode.RANGE, start=2, count=2))
    assert reversed_data.row_ids.gather(
        audio_positions(reversed_data, ranged, ())
    ).to_list() == [3, 2]


def test_nonfinite_channel_denominators_and_empty_record_remain_explicit(
    tmp_path: Path,
) -> None:
    inputs, _ = fixture(tmp_path)
    sf.write(
        tmp_path / "a.wav",
        np.array([[np.nan, 0], [np.inf, 1]]),
        4,
        subtype="DOUBLE",
    )
    sf.write(tmp_path / "b.wav", np.empty((0, 2)), 4, subtype="DOUBLE")
    store = ArrayStore(retained_bytes=0)
    try:
        result = scan(inputs[0], store)
        assert result.records["nonfinite_fraction"].to_list() == [1, None]
        assert result.records["silence_fraction"].to_list() == [0, None]
        assert result.records["duration"].to_list() == [0.5, 0]
        assert result.channel_records["finite"].to_list() == [0, 2, 0, 0]
        assert result.channel_records["rms"].to_list() == [None, 2**-0.5, None, None]
        assert result.channel_records["clipped_fraction"].to_list() == [
            None,
            0.5,
            None,
            None,
        ]
        assert result.channel_records["silent_fraction"].to_list() == [
            None,
            0.5,
            None,
            None,
        ]
    finally:
        store.close()


def test_array_header_unknown_rate_and_exact_single_lease_preserve_raw_values(
    tmp_path: Path,
) -> None:
    path = tmp_path / "waves.npz"
    waves = np.array([[0, 0, 0, 0], [-32768, 0, 32767, 0]], dtype=np.int16)
    np.savez_compressed(path, waves=waves)
    before = path.read_bytes()
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping("waves", layout=ArrayLayout.AUDIO, display_axes=(1,))
    dataset = Dataset.from_source(
        pl.DataFrame({"record_index": [0, 1]}), catalog.source
    )
    source = replace(
        fixture(tmp_path)[0][0].source, profile=AudioCollectionSettings("waves")
    )
    item = AudioComparisonInput(
        source, dataset, "arrays", catalog=catalog, mapping=mapping
    )
    store = ArrayStore(retained_bytes=0, directory=tmp_path)
    try:
        headers = scan(item, store)
        assert headers.records["duration"].null_count() == 2 and store.extractions == 0
        exact = replace(
            item,
            source=replace(
                source, profile=replace(source.profile, mode=AudioProfileMode.SIGNAL)
            ),
        )
        with pytest.raises(ValueError, match="sample rate"):
            scan(exact, store)
        exact = replace(
            exact,
            source=replace(
                exact.source, profile=replace(exact.source.profile, array_sample_rate=4)
            ),
        )
        result = scan(exact, store)
        assert result.records["duration"].to_list() == [1, 1]
        assert result.channel_records["minimum"].to_list() == ["0", "-32768"]
        assert result.channel_records["peak_original"].to_list() == ["0.0", "32768.0"]
        assert result.channel_records["family"].to_list() == ["array units · int16"] * 2
        assert result.channel_records["clipped_fraction"].to_list() == [0, 0.5]
        assert store.extractions == 1 and store.stored_bytes == 0
    finally:
        temporary = store.temporary_path
        store.close()
    assert (
        temporary is not None and not temporary.exists() and path.read_bytes() == before
    )
