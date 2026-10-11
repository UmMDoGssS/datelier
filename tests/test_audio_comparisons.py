"""Unequal source sizes, compatible units, exact bins and isolated linked selection."""

from concurrent.futures import CancelledError
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
from datelier.inspection.audio.collections.scan import scan_collection
from datelier.inspection.audio.collections.settings import (
    AudioCollectionSettings,
    AudioProfileMode,
)
from datelier.inspection.audio.collections.types import (
    AudioCollectionProfile,
    CollectionProgress,
)
from datelier.inspection.audio.comparisons.prepare import prepare_comparison
from datelier.inspection.audio.comparisons.selection import select_bin
from datelier.inspection.audio.comparisons.settings import (
    AudioComparisonSettings,
    AudioComparisonSource,
)
from datelier.inspection.audio.comparisons.types import (
    AudioComparisonInput,
    PreparedAudioComparison,
)
from datelier.inspection.audio.types import AudioLocator
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays import ArrayStore
from datelier.io.arrays.metadata import inspect_arrays


def prepare(
    inputs: tuple[AudioComparisonInput, ...], recipe: AudioComparisonSettings
) -> PreparedAudioComparison:
    return prepare_comparison(inputs, recipe, Event(), CollectionProgress())


def test_common_duration_bins_and_normalization_exclude_failed_records(
    tmp_path: Path,
) -> None:
    inputs, recipe = fixture(tmp_path)
    before = {path: path.read_bytes() for path in tmp_path.iterdir()}
    result = prepare(inputs, recipe)
    duration = next(c for c in result.curves if c.metric.name == "Duration")
    assert duration.edges.tolist() == [1, 1.5, 2]
    assert all(c is not None and c.tolist() == [0, 1, 1, 0] for c in duration.counts)
    assert all(c is not None and c.sum() == 1 for c in duration.proportions)
    rates = next(c for c in result.curves if c.metric.name == "Sample rate")
    assert rates.edges.tolist() == [4, 6, 8]
    assert rates.counts[0] is not None and rates.counts[0].tolist() == [0, 2, 0, 0]
    assert duration.summaries[1] is not None and duration.summaries[1].mean == 1.5
    rms = next(
        c for c in result.curves if c.metric.name == "RMS" and c.metric.channel == 0
    )
    assert (
        rms.metric.family == "full-scale amplitude"
        and rms.minimum == 0
        and rms.maximum == 0.5
    )
    assert result.profiles[0].file_id != result.profiles[1].file_id
    assert all(path.read_bytes() == value for path, value in before.items())


def test_sorted_source_selection_keeps_equal_row_numbers_separate(
    tmp_path: Path,
) -> None:
    inputs, recipe = fixture(tmp_path)
    original = inputs[1].dataset
    inputs = (
        inputs[0],
        replace(
            inputs[1],
            dataset=original.with_rows(
                original.table.reverse(), original.row_ids.reverse()
            ),
        ),
    )
    result = prepare(inputs, recipe)
    duration = next(c for c in result.curves if c.metric.name == "Duration")
    selected = select_bin(result, 1, duration.metric, 1, inputs[1].dataset)
    assert selected.origin.file_id == "test" and selected.origin.view == "records"
    assert selected.row_ids == (1,) and selected.first_position == 3
    first = select_bin(result, 0, duration.metric, 0, inputs[0].dataset)
    assert first.origin.file_id == "train" and first.row_ids == (0,)
    with pytest.raises(ValueError, match="changed"):
        select_bin(
            result,
            1,
            duration.metric,
            1,
            inputs[1].dataset.with_rows(original.table, original.row_ids),
        )


def test_file_and_array_amplitudes_remain_separate_but_seconds_share_bins(
    tmp_path: Path,
) -> None:
    inputs, _ = fixture(tmp_path)
    path = tmp_path / "waves.npz"
    np.savez_compressed(path, waves=np.array([[0, 2, 0, -2]], dtype=np.float32))
    catalog = inspect_arrays(path)
    mapping = ArrayRecordMapping("waves", layout=ArrayLayout.AUDIO, display_axes=(1,))
    dataset = Dataset.from_source(pl.DataFrame({"record_index": [0]}), catalog.source)
    source = AudioComparisonSource(
        "array",
        AudioCollectionSettings(
            "waves", mode=AudioProfileMode.SIGNAL, array_sample_rate=4
        ),
    )
    item = AudioComparisonInput(
        source, dataset, "array", catalog=catalog, mapping=mapping
    )
    result = prepare(
        (inputs[0], item), AudioComparisonSettings((inputs[0].source, source), 2)
    )
    rms = [c for c in result.curves if c.metric.name == "RMS" and c.metric.channel == 0]
    assert {c.metric.family for c in rms} == {
        "array amplitude · float32",
        "full-scale amplitude",
    }
    assert all(sum(chart is not None for chart in c.counts) == 1 for c in rms)
    duration = next(c for c in result.curves if c.metric.name == "Duration")
    assert all(chart is not None for chart in duration.counts)
    array_rms = next(c for c in rms if c.metric.family.startswith("array"))
    assert array_rms.summaries[1] is not None and array_rms.summaries[
        1
    ].mean == pytest.approx(2**0.5)


def test_huge_scalar_axes_are_scaled_with_original_values_retained(
    tmp_path: Path,
) -> None:
    inputs, _ = fixture(tmp_path)
    for name, amplitude in (("a", -1e300), ("b", 1e300)):
        sf.write(tmp_path / f"{name}.wav", np.full(4, amplitude), 4, subtype="DOUBLE")
    result = prepare(
        inputs, AudioComparisonSettings(tuple(i.source for i in inputs), 2)
    )
    mean = next(c for c in result.curves if c.metric.name == "Mean")
    assert mean.scaled and mean.edges.tolist() == [0, 0.5, 1]
    assert mean.minimum == -1e300 and mean.maximum == 1e300
    assert mean.summaries[0] is not None and mean.summaries[0].mean == 0
    assert select_bin(result, 0, mean.metric, 0, inputs[0].dataset).row_ids == (0,)
    assert all(
        np.longdouble(value) == np.longdouble(1e300)
        for value in result.profiles[0].channel_records["peak_original"]
    )


def test_late_asset_edit_rejects_earlier_contributor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs, recipe = fixture(tmp_path)
    calls = 0

    def changed(
        dataset: Dataset,
        file_id: str,
        view_name: str,
        settings: AudioCollectionSettings,
        selection: tuple[int, ...],
        references: ReferenceSettings,
        index: ReferenceIndex | None,
        arrays: ArrayStore,
        stop: Event,
        progress: CollectionProgress,
        catalog: object = None,
        mapping: object = None,
    ) -> tuple[AudioCollectionProfile, tuple[AudioLocator, ...]]:
        nonlocal calls
        # Fixture here uses file references, without array arguments.
        assert catalog is None and mapping is None
        result = scan_collection(
            dataset,
            file_id,
            view_name,
            settings,
            selection,
            references,
            index,
            arrays,
            stop,
            progress,
        )
        calls += 1
        if calls == 2:
            sf.write(tmp_path / "a.wav", np.zeros(8), 4, subtype="DOUBLE")
        return result

    monkeypatch.setattr(
        "datelier.inspection.audio.comparisons.prepare.scan_collection", changed
    )
    with pytest.raises(ValueError, match="changed"):
        prepare(inputs, recipe)


def test_invalid_or_abandoned_comparison_has_no_partial_result(tmp_path: Path) -> None:
    inputs, recipe = fixture(tmp_path)
    with pytest.raises(ValueError, match="two"):
        prepare(inputs[:1], recipe)
    stop = Event()
    stop.set()
    with pytest.raises(CancelledError):
        prepare_comparison(inputs, recipe, stop, CollectionProgress())
    with pytest.raises(ValueError, match="one audio"):
        AudioComparisonSettings((recipe.sources[0], recipe.sources[0])).validate()
