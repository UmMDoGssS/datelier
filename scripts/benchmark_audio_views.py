"""Long waveform/spectral resources, temporary arrays and source integrity."""

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
from datelier.inspection.audio.decoding import audio_metadata, locate_audio
from datelier.inspection.audio.signal import AudioViewKind, SignalViewSettings
from datelier.inspection.audio.signal.spectra import prepare_spectrogram
from datelier.inspection.audio.signal.waveforms import prepare_waveform
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
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mel", action="store_true")
    args = parser.parse_args()
    mode = AudioViewKind.MEL if args.mel else AudioViewKind.SPECTROGRAM
    baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    with TemporaryDirectory(prefix="datelier-audio-views-") as temporary:
        root = Path(temporary)
        path = root / "long.wav"
        rate, frames = 48000, 48000 * 600
        positions = np.arange(65536)
        with sf.SoundFile(
            path, "w", samplerate=rate, channels=2, subtype="FLOAT"
        ) as stream:
            for start in range(0, frames, len(positions)):
                values = 0.25 * np.sin(2 * np.pi * 1500 * (positions + start) / rate)
                stream.write(
                    np.stack((values, -values), axis=1)[
                        : min(len(values), frames - start)
                    ]
                )
        before = digest(path)
        dataset = load_media(path).dataset
        locator = locate_audio(
            dataset, "file", "", "path", 0, ReferenceSettings(), None
        )
        metadata = audio_metadata(locator)
        arrays = ArrayStore(retained_bytes=1024 * 1024, directory=root)
        started = perf_counter()
        envelope = prepare_waveform(
            locator, metadata, AudioRange(), 0, SignalViewSettings(), arrays
        )
        waveform_seconds = perf_counter() - started
        assert (
            envelope.minimum.astype(np.float64).min() == -0.25
            and envelope.maximum.astype(np.float64).max() == 0.25
        )
        assert waveform_seconds < 2 and envelope.retained_bytes < 16 * 1024 * 1024
        started = perf_counter()
        spectrum = prepare_spectrogram(
            locator,
            metadata,
            AudioRange(frames - rate * 60, frames),
            0,
            SignalViewSettings(mode=mode),
            arrays,
        )
        spectral_seconds = perf_counter() - started
        peak = float(spectrum.frequencies[int(spectrum.power[:, 0].argmax())])
        assert 1350 < peak < 1650 if args.mel else peak == 1500
        assert spectral_seconds < 10 and spectrum.retained_bytes <= 16 * 1024 * 1024
        assert arrays.temporary_path is None and digest(path) == before
        file_report = {
            "waveform_seconds": waveform_seconds,
            "waveform_retained_bytes": envelope.retained_bytes,
            "spectral_seconds": spectral_seconds,
            "spectral_retained_bytes": spectrum.retained_bytes,
            "spectral_shape": list(spectrum.power.shape),
            "spectral_frames": spectrum.spectral_frames,
            "time_step": spectrum.time_step,
            "frequency_step": spectrum.frequency_step,
            "peak_hz": peak,
            "view": mode.value,
            "file_temporary_bytes": 0,
        }
        del spectrum, envelope
        archive = root / "waves.npz"
        waves = np.zeros((10, 48000, 2), dtype=np.float32)
        waves[9, :, 0] = 0.25 * np.sin(2 * np.pi * 1500 * np.arange(48000) / rate)
        waves[9, :, 1] = -waves[9, :, 0]
        np.savez_compressed(archive, waves=waves)
        del waves
        array_before = digest(archive)
        catalog = inspect_arrays(archive)
        mapping = ArrayRecordMapping(
            "waves", layout=ArrayLayout.AUDIO, display_axes=(1,), channel_axis=2
        )
        table, _ = prepare_array_records(arrays, catalog, mapping)
        locator = locate_audio(
            table,
            "arrays",
            "waves",
            "waves",
            9,
            ReferenceSettings(),
            None,
            catalog,
            mapping,
        )
        metadata = audio_metadata(locator, rate)
        started = perf_counter()
        spectrum = prepare_spectrogram(
            locator,
            metadata,
            AudioRange(),
            1,
            SignalViewSettings(mode=mode, fft=65536, mel_bands=512)
            if args.mel
            else SignalViewSettings(mode=mode),
            arrays,
        )
        array_seconds = perf_counter() - started
        assert arrays.extractions == 1 and arrays.stored_bytes == 0
        peak = float(spectrum.frequencies[int(spectrum.power[:, 0].argmax())])
        assert 1480 < peak < 1520 if args.mel else peak == 1500
        temporary_path = arrays.temporary_path
        arrays.close()
        assert (
            temporary_path is not None
            and not temporary_path.exists()
            and digest(archive) == array_before
        )
        rss_increase = (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - baseline
        ) * 1024
        assert rss_increase < 96 * 1024 * 1024
        report = {
            **file_report,
            "array_seconds": array_seconds,
            "array_shape": list(spectrum.power.shape),
            "array_fft": spectrum.settings.fft,
            "array_peak_hz": peak,
            "array_extractions": arrays.extractions,
            "array_peak_temporary_bytes": arrays.extracted_bytes,
            "array_retained_bytes_after_view": arrays.stored_bytes,
            "peak_rss_increase_bytes": rss_increase,
            "source_preserved": True,
            "temporary_cleanup": True,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
