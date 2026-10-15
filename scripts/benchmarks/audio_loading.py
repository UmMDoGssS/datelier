"""Fresh-process audio header/window latency, byte budgets and lease cleanup."""

import argparse
import hashlib
import json
import resource
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import numpy as np
import soundfile as sf

from datelier.inspection.arrays import ArrayLayout, ArrayRecordMapping
from datelier.inspection.audio.decoding import (
    audio_blocks,
    audio_metadata,
    locate_audio,
    prepare_window,
)
from datelier.inspection.audio.profiles import AudioThresholds
from datelier.inspection.audio.profiles.statistics import profile_signal
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.references import ReferenceSettings
from datelier.io.arrays import ArrayStore
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.records import prepare_array_records
from datelier.io.media import load_media


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    with TemporaryDirectory(prefix="datelier-audio-loading-") as temporary:
        root = Path(temporary)
        path = root / "long.wav"
        rate, frames = 48000, 48000 * 600
        block = np.full((65536, 2), 0.25, dtype=np.float64)
        with sf.SoundFile(
            path, "w", samplerate=rate, channels=2, subtype="PCM_16"
        ) as stream:
            for start in range(0, frames, len(block)):
                stream.write(block[: min(len(block), frames - start)])
        before = digest(path)
        started = perf_counter()
        dataset = load_media(path).dataset
        locator = locate_audio(
            dataset, "file", "", "path", 0, ReferenceSettings(), None
        )
        metadata = audio_metadata(locator)
        header_seconds = perf_counter() - started
        assert (metadata.duration, metadata.channels, metadata.sample_rate) == (
            600,
            2,
            rate,
        )
        store = ArrayStore(retained_bytes=1024 * 1024, directory=root)
        started = perf_counter()
        window = prepare_window(
            locator, metadata, AudioRange(frames - rate, frames), store
        )
        first_seconds = perf_counter() - started
        assert window.raw.shape == (rate, 2) and np.all(window.raw == 0.25)
        assert window.retained_bytes <= 16 * 1024 * 1024
        assert store.temporary_path is None and store.extractions == 0
        counted = largest = 0
        with audio_blocks(locator, metadata, store) as blocks:
            for decoded in blocks:
                counted += len(decoded.samples)
                largest = max(largest, decoded.samples.nbytes)
        assert counted == frames and largest <= 1024 * 1024
        started = perf_counter()
        profile = profile_signal(
            locator, metadata, AudioRange(), AudioThresholds(), store
        )
        profile_seconds = perf_counter() - started
        assert profile.frames == frames and profile.duration == 600
        assert all(
            channel.rms == channel.mean == 0.25
            and channel.clipped == channel.silent == 0
            for channel in profile.channels
        )
        assert profile_seconds < 10
        assert digest(path) == before
        archive = root / "waves.npz"
        waves = np.full((20, 48000, 2), 0.125, dtype=np.float32)
        np.savez_compressed(archive, waves=waves)
        del waves
        array_before = digest(archive)
        catalog = inspect_arrays(archive)
        mapping = ArrayRecordMapping(
            "waves", layout=ArrayLayout.AUDIO, display_axes=(1,), channel_axis=2
        )
        table, _ = prepare_array_records(store, catalog, mapping)
        locator = locate_audio(
            table,
            "arrays",
            "waves",
            "waves",
            19,
            ReferenceSettings(),
            None,
            catalog,
            mapping,
        )
        started = perf_counter()
        metadata = audio_metadata(locator, rate)
        array_metadata_seconds = perf_counter() - started
        assert store.extractions == 0
        started = perf_counter()
        window = prepare_window(locator, metadata, AudioRange(rate - 500, rate), store)
        array_window_seconds = perf_counter() - started
        assert np.all(window.raw == 0.125) and window.raw.shape == (500, 2)
        assert store.extractions == 1 and store.stored_bytes == 0
        temporary_path = store.temporary_path
        store.close()
        assert temporary_path is not None and not temporary_path.exists()
        assert digest(archive) == array_before
        rss_increase = (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - baseline
        ) * 1024
        assert (
            header_seconds < 0.5
            and first_seconds < 2
            and rss_increase < 64 * 1024 * 1024
        )
        report = {
            "file_frames": frames,
            "file_duration_seconds": 600,
            "header_seconds": header_seconds,
            "exact_window_seconds": first_seconds,
            "decoded_frames": counted,
            "largest_block_bytes": largest,
            "file_temporary_bytes": 0,
            "exact_profile_seconds": profile_seconds,
            "exact_profile_frames": profile.frames,
            "exact_profile_rms": [channel.rms for channel in profile.channels],
            "array_metadata_seconds": array_metadata_seconds,
            "array_window_seconds": array_window_seconds,
            "array_extractions": store.extractions,
            "array_peak_temporary_bytes": store.extracted_bytes,
            "array_retained_bytes_after_window": store.stored_bytes,
            "peak_rss_increase_bytes": rss_increase,
            "source_preserved": True,
            "temporary_cleanup": True,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
