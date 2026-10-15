"""Installed-wheel mixed file/array comparisons, signal views and lazy runtimes."""

import argparse
import hashlib
import importlib.util
import json
import platform
import resource
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import perf_counter

import numpy as np
import soundfile as sf

import datelier
from datelier.gui.fonts import FALLBACK_FONTS
from datelier.inspection.arrays import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
)
from datelier.inspection.arrays.settings import SliceSettings
from datelier.inspection.audio.collections.settings import (
    AudioCollectionSettings,
    AudioProfileMode,
)
from datelier.inspection.audio.collections.types import CollectionProgress
from datelier.inspection.audio.comparisons import (
    AudioComparisonSettings,
    AudioComparisonSource,
)
from datelier.inspection.audio.comparisons.prepare import (
    prepare_comparison as audio_compare,
)
from datelier.inspection.audio.comparisons.types import AudioComparisonInput
from datelier.inspection.audio.decoding import audio_metadata, locate_audio
from datelier.inspection.audio.playback.outputs import discover_outputs
from datelier.inspection.audio.signal import AudioViewKind, SignalViewSettings
from datelier.inspection.audio.signal.spectra import prepare_spectrogram
from datelier.inspection.audio.signal.waveforms import prepare_waveform
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.checkpoints.slices import prepare_tensor_slice
from datelier.inspection.images.comparisons.prepare import (
    prepare_comparison as image_compare,
)
from datelier.inspection.images.comparisons.settings import (
    ImageComparisonSettings,
    ImageComparisonSource,
)
from datelier.inspection.images.comparisons.types import ImageComparisonInput
from datelier.inspection.images.profiles import ImageProfileSettings, ImageProgress
from datelier.inspection.references import ReferenceSettings
from datelier.inspection.text.comparisons import (
    TextComparisonSettings,
    TextComparisonSource,
)
from datelier.inspection.text.comparisons.prepare import (
    prepare_comparison as text_compare,
)
from datelier.inspection.text.comparisons.types import TextComparisonInput
from datelier.inspection.text.profiles.corpus import TextProgress
from datelier.inspection.text.types import CorpusMode, TextScope, TextSource
from datelier.io.arrays import ArrayStore
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.records import prepare_array_records
from datelier.io.checkpoints.storage import CheckpointStore
from datelier.io.importing import load_file
from scripts.support.multimodal import MultimodalFixtures, make_multimodal


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mixed(fixtures: MultimodalFixtures) -> dict[str, object]:
    datasets = tuple(load_file(p).dataset for p in (fixtures.train, fixtures.test))
    names = ("train", "test")
    references = ReferenceSettings(roots=(str(fixtures.train.parent),))
    text_sources = tuple(
        TextComparisonSource(
            name, "caption", TextSource.INLINE, scope=TextScope(CorpusMode.COLLECTION)
        )
        for name in names
    )
    image_sources = tuple(
        ImageComparisonSource(name, ImageProfileSettings("image")) for name in names
    )
    audio_sources = tuple(
        AudioComparisonSource(
            name, AudioCollectionSettings("audio", mode=AudioProfileMode.SIGNAL)
        )
        for name in names
    )
    started = perf_counter()
    text = text_compare(
        tuple(
            TextComparisonInput(source, dataset, source.file_id)
            for source, dataset in zip(text_sources, datasets, strict=True)
        ),
        TextComparisonSettings(text_sources),
        Event(),
        TextProgress(),
    )
    images = image_compare(
        tuple(
            ImageComparisonInput(source, dataset, source.file_id, references=references)
            for source, dataset in zip(image_sources, datasets, strict=True)
        ),
        ImageComparisonSettings(image_sources, bins=8),
        Event(),
        ImageProgress(),
    )
    audio = audio_compare(
        tuple(
            AudioComparisonInput(source, dataset, source.file_id, references=references)
            for source, dataset in zip(audio_sources, datasets, strict=True)
        ),
        AudioComparisonSettings(audio_sources, bins=8),
        Event(),
        CollectionProgress(),
    )
    seconds = perf_counter() - started
    assert [p.documents for p in text.profiles] == [2, 3]
    assert [p.ready for p in images.profiles] == [2, 3]
    assert [p.ready for p in audio.profiles] == [2, 3]
    assert audio.profiles[0].records["duration"].to_list() == [1, 2]
    assert audio.profiles[1].records["duration"].to_list() == [3, 1, 2]
    assert [p.total_pixels for p in images.profiles] == [480, 864]
    assert all(p.file_id == name for p, name in zip(audio.profiles, names, strict=True))
    arrays = ArrayStore(retained_bytes=1, directory=fixtures.train.parent)
    try:
        locator = locate_audio(datasets[0], "train", "", "audio", 0, references, None)
        metadata = audio_metadata(locator)
        envelope = prepare_waveform(
            locator, metadata, AudioRange(), 0, SignalViewSettings(), arrays
        )
        assert (
            envelope.minimum.astype(np.float64).min() == -0.25
            and envelope.maximum.astype(np.float64).max() == 0.25
        )
        spectra = []
        for mode in (AudioViewKind.SPECTROGRAM, AudioViewKind.MEL):
            spectrum = prepare_spectrogram(
                locator,
                metadata,
                AudioRange(),
                0,
                SignalViewSettings(mode=mode, fft=256, hop=64, mel_bands=32),
                arrays,
            )
            peak = float(spectrum.frequencies[int(spectrum.power[:, 0].argmax())])
            assert 420 < peak < 580 if mode == AudioViewKind.MEL else peak == 500
            spectra.append({"view": mode.value, "peak_hz": peak})
        catalog = inspect_arrays(fixtures.arrays)
        mapping = ArrayRecordMapping(
            "audio",
            layout=ArrayLayout.AUDIO,
            display_axes=(1,),
            channel_axis=2,
            supporting=(
                SupportingArray("labels", "label"),
                SupportingArray("captions", "caption"),
            ),
        )
        dataset, _ = prepare_array_records(arrays, catalog, mapping)
        dataset = dataset.with_rows(dataset.table.reverse(), dataset.row_ids.reverse())
        source = AudioComparisonSource(
            "array",
            replace(audio_sources[0].profile, column="audio", array_sample_rate=8000),
        )
        array_result = audio_compare(
            (
                AudioComparisonInput(
                    audio_sources[0], datasets[0], "train", references=references
                ),
                AudioComparisonInput(
                    source,
                    dataset,
                    "array",
                    "audio",
                    arrays=arrays,
                    catalog=catalog,
                    mapping=mapping,
                ),
            ),
            AudioComparisonSettings((audio_sources[0], source), bins=8),
            Event(),
            CollectionProgress(),
        )
        assert array_result.profiles[1].records["row_id"].to_list() == [2, 1, 0]
        assert dataset.table["caption"].to_list()[1] == "array b e\u0301"
        rms_families = {
            c.metric.family for c in array_result.curves if c.metric.name == "RMS"
        }
        assert rms_families == {"full-scale amplitude", "array amplitude · float32"}
        assert arrays.stored_bytes == 0
        temporary = arrays.temporary_path
        retained = sum(
            result.retained_bytes for result in (text, images, audio, array_result)
        )
        assert retained < 16 * 1024 * 1024 and seconds < 3
    finally:
        arrays.close()
    assert temporary is not None and not temporary.exists()
    return {
        "comparison_seconds": seconds,
        "text_documents": [2, 3],
        "image_records": [2, 3],
        "audio_records": [2, 3],
        "array_row_ids": [2, 1, 0],
        "spectra": spectra,
        "prepared_bytes": retained,
        "array_disk_after": arrays.stored_bytes,
        "array_directory_removed": True,
    }


def checkpoint(root: Path) -> dict[str, object]:
    import torch

    path = root / "dense.pt"
    torch.save(
        {"weight": torch.arange(24, dtype=torch.float32).reshape(2, 3, 4), "epoch": 7},
        path,
    )
    before = digest(path)
    imported = load_file(path)
    catalog = imported.checkpoint_catalog
    assert catalog and catalog.mapped
    store = CheckpointStore(retained_bytes=1)
    try:
        result = prepare_tensor_slice(
            store,
            catalog,
            SliceSettings("$['weight']", axes=(1, 2), fixed=(1, 0, 0), counts=(3, 4)),
        )
        np.testing.assert_array_equal(result.view.raw, np.arange(12, 24).reshape(3, 4))
        assert store.stored_bytes == 0
    finally:
        store.close()
    assert digest(path) == before and torch.version.cuda is None
    return {
        "torch": str(torch.__version__),
        "cpu_values": True,
        "mapped": catalog.mapped,
        "source_preserved": True,
        "retained_bytes": store.stored_bytes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoints", action="store_true")
    args = parser.parse_args()
    module = Path(datelier.__file__).resolve()
    assert "site-packages" in module.parts
    assert "torch" not in sys.modules and "sounddevice" not in sys.modules
    font = FALLBACK_FONTS[-1]
    assert font.with_name("OFL-NotoEmoji.txt").is_file()
    assert (
        digest(font)
        == "de6c18832938afc99caf132b39d6a30a19bac7f2e812e28db2535b4608d27551"
    )
    baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    with TemporaryDirectory(prefix="datelier-installed-mixed-") as temporary:
        root = Path(temporary)
        fixtures = make_multimodal(root)
        before = {p: digest(p) for p in fixtures.sources}
        report = mixed(fixtures)
        mixed_peak_mb = (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - baseline
        ) / 1024
        assert mixed_peak_mb < 128
        report["mixed_peak_rss_increase_mb"] = mixed_peak_mb
        assert all(digest(p) == value for p, value in before.items())
        assert "torch" not in sys.modules and "sounddevice" not in sys.modules
        report["idle_optional_runtimes"] = True
        report["checkpoint_available"] = importlib.util.find_spec("torch") is not None
        assert report["checkpoint_available"] == args.checkpoints
        if args.checkpoints:
            report["checkpoint"] = checkpoint(root)
    peak_mb = (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - baseline) / 1024
    report["checkpoint_peak_rss_increase_mb"] = peak_mb - mixed_peak_mb
    choices = discover_outputs()
    assert choices
    report.update(
        {
            "python": platform.python_version(),
            "module": str(module),
            "soundfile": sf.__version__,
            "libsndfile": sf.__libsndfile_version__,
            "peak_rss_increase_mb": peak_mb,
            "outputs": [c.query for c in choices],
            "source_preserved": True,
            "packaged_font_sha256": digest(font),
            "playback_started": False,
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
