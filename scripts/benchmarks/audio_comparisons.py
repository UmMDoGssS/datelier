"""Unequal header collections, long exact scans and compressed collection resources."""

import argparse
import hashlib
import json
import resource
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import perf_counter

import numpy as np
import polars as pl
import soundfile as sf

from datelier.core import Dataset, SourceReference
from datelier.inspection.arrays import ArrayLayout, ArrayRecordMapping
from datelier.inspection.audio.collections.settings import (
    AudioCollectionSettings,
    AudioProfileMode,
)
from datelier.inspection.audio.collections.types import CollectionProgress
from datelier.inspection.audio.comparisons import (
    AudioComparisonSettings,
    AudioComparisonSource,
)
from datelier.inspection.audio.comparisons.prepare import prepare_comparison
from datelier.inspection.audio.comparisons.types import AudioComparisonInput
from datelier.io.arrays import ArrayStore
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.records import prepare_array_records


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def references(root: Path, name: str, rows: int) -> AudioComparisonInput:
    path = root / f"{name}.csv"
    path.write_text("audio\n")
    stat = path.stat()
    dataset = Dataset.from_source(
        pl.DataFrame({"audio": ["long.wav"] * rows}),
        SourceReference(path, stat.st_size, stat.st_mtime_ns),
    )
    source = AudioComparisonSource(name, AudioCollectionSettings("audio"))
    return AudioComparisonInput(source, dataset, name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    with TemporaryDirectory(prefix="datelier-audio-comparisons-") as temporary:
        root = Path(temporary)
        path = root / "long.wav"
        rate, frames = 48000, 48000 * 600
        block = np.full((65536, 2), 0.25, dtype=np.float32)
        with sf.SoundFile(
            path, "w", samplerate=rate, channels=2, subtype="FLOAT"
        ) as stream:
            for first in range(0, frames, len(block)):
                stream.write(block[: min(len(block), frames - first)])
        before = digest(path)
        inputs = (references(root, "train", 10000), references(root, "test", 5000))
        recipe = AudioComparisonSettings(tuple(i.source for i in inputs))
        started = perf_counter()
        headers = prepare_comparison(inputs, recipe, Event(), CollectionProgress())
        header_seconds = perf_counter() - started
        assert header_seconds < 10 and headers.retained_bytes < 16 * 1024**2
        assert [p.records.height for p in headers.profiles] == [10000, 5000]
        assert all(p.channel_records.is_empty() for p in headers.profiles)
        duration = next(c for c in headers.curves if c.metric.name == "Duration")
        assert all(
            summary is not None and summary.mean == 600
            for summary in duration.summaries
        )
        report: dict[str, object] = {
            "header_seconds": header_seconds,
            "header_records": [10000, 5000],
            "header_retained_bytes": headers.retained_bytes,
        }
        del headers
        exact_inputs = tuple(
            replace(
                i,
                dataset=i.dataset.with_rows(
                    i.dataset.table.head(1), i.dataset.row_ids.head(1)
                ),
                source=replace(
                    i.source,
                    profile=replace(i.source.profile, mode=AudioProfileMode.SIGNAL),
                ),
            )
            for i in inputs
        )
        exact_recipe = replace(recipe, sources=tuple(i.source for i in exact_inputs))
        started = perf_counter()
        signals = prepare_comparison(
            exact_inputs, exact_recipe, Event(), CollectionProgress()
        )
        signal_seconds = perf_counter() - started
        assert signal_seconds < 20 and signals.retained_bytes < 16 * 1024**2
        assert all(
            p.channel_records["rms"].to_list() == [0.25, 0.25] for p in signals.profiles
        )
        report.update(
            signal_seconds=signal_seconds,
            signal_retained_bytes=signals.retained_bytes,
            signal_frames_per_source=frames,
        )
        archive = root / "waves.npz"
        waves = np.zeros((10, 48000, 2), dtype=np.float32)
        waves[9] = 0.5
        np.savez_compressed(archive, waves=waves)
        del waves
        array_before = digest(archive)
        arrays = ArrayStore(retained_bytes=1024**2, directory=root)
        catalog = inspect_arrays(archive)
        mapping = ArrayRecordMapping(
            "waves", layout=ArrayLayout.AUDIO, display_axes=(1,), channel_axis=2
        )
        dataset, _ = prepare_array_records(arrays, catalog, mapping)
        source = AudioComparisonSource(
            "arrays",
            AudioCollectionSettings(
                "waves", mode=AudioProfileMode.SIGNAL, array_sample_rate=rate
            ),
        )
        item = AudioComparisonInput(
            source, dataset, "arrays", arrays=arrays, catalog=catalog, mapping=mapping
        )
        started = perf_counter()
        compared = prepare_comparison(
            (exact_inputs[0], item),
            AudioComparisonSettings((exact_inputs[0].source, source)),
            Event(),
            CollectionProgress(),
        )
        array_seconds = perf_counter() - started
        assert arrays.extractions == 1 and arrays.stored_bytes == 0
        profile = compared.profiles[1]
        assert profile.records.height == 10 and profile.channel_records.height == 20
        assert profile.channel_records["rms"].tail(2).to_list() == [0.5, 0.5]
        assert compared.retained_bytes < 16 * 1024**2
        temporary_path = arrays.temporary_path
        arrays.close()
        assert temporary_path is not None and not temporary_path.exists()
        assert digest(path) == before and digest(archive) == array_before
        rss_increase = (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - baseline
        ) * 1024
        assert rss_increase < 96 * 1024**2
        report.update(
            array_comparison_seconds=array_seconds,
            array_extractions=arrays.extractions,
            array_peak_temporary_bytes=arrays.extracted_bytes,
            array_retained_after_command=arrays.stored_bytes,
            comparison_retained_bytes=compared.retained_bytes,
            peak_rss_increase_bytes=rss_increase,
            source_preserved=True,
            temporary_cleanup=True,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
