"""Repeated mixed-file/view jobs, oversized array eviction and complete closure."""

import argparse
import hashlib
import json
import resource
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, perf_counter, sleep

import numpy as np

from datelier.application.sessions import EditorController, FileController
from datelier.inspection.arrays import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
)
from datelier.inspection.audio.collections.settings import (
    AudioCollectionSettings,
    AudioProfileMode,
)
from datelier.inspection.audio.comparisons import (
    AudioComparisonSettings,
    AudioComparisonSource,
)
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.images.comparisons.settings import (
    ImageComparisonSettings,
    ImageComparisonSource,
)
from datelier.inspection.images.profiles import ImageProfileSettings
from datelier.inspection.images.types import ImageDisplay, ImageWindow
from datelier.inspection.references import ReferenceSettings
from datelier.inspection.text.comparisons import (
    TextComparisonSettings,
    TextComparisonSource,
)
from datelier.inspection.text.types import CorpusMode, TextScope, TextSource
from datelier.io.jobs import LoadPhase
from datelier.io.types import ArrayOptions
from datelier.pipeline import Sort
from scripts.support.multimodal import make_multimodal


def wait(editor: EditorController, ready: Callable[[], bool]) -> float:
    started = perf_counter()
    deadline = monotonic() + 3
    while monotonic() < deadline:
        editor.poll()
        if ready():
            return perf_counter() - started
        sleep(0.001)
    raise AssertionError("Mixed fixture command exceeded three seconds")


def settled(editor: EditorController) -> bool:
    return all(
        f.loader.status.phase != LoadPhase.LOADING
        and not f.editor.busy
        and not f.record_views.pending
        and not f.references.busy
        and not f.images.jobs.busy
        and not f.audio.jobs.busy
        and not f.text.jobs.busy
        for f in editor.all_files
    )


def view(owner: FileController, member: str, layout: ArrayLayout) -> FileController:
    return owner.record_views.open_array(
        owner,
        ArrayRecordMapping(
            member,
            layout=layout,
            display_axes=(1, 2) if layout == ArrayLayout.IMAGE else (1,),
            channel_axis=3 if layout == ArrayLayout.IMAGE else 2,
            supporting=(
                SupportingArray("labels", "label"),
                SupportingArray("captions", "caption"),
            ),
        ),
    )


def records(editor: EditorController, file: FileController) -> None:
    active = file.loader.active
    assert active is not None
    options = active.imported.options
    mapping = options.mapping if isinstance(options, ArrayOptions) else None
    if mapping is not None and mapping.layout == ArrayLayout.IMAGE:
        file.images.jobs.request_record(
            active.dataset, mapping.member, 0, file.arrays.catalog, mapping
        )
    else:
        file.audio.jobs.request_record(
            active.dataset,
            "audio",
            0,
            file.arrays.catalog,
            mapping,
            file.audio.settings.array_sample_rate,
        )
    wait(editor, lambda: not file.images.jobs.busy and not file.audio.jobs.busy)


def cycle(editor: EditorController, root: Path) -> dict[str, object]:
    csv, test, owner = (
        editor.new_file(root / name)
        for name in ("train.csv", "test.csv", "records.npz")
    )
    load_seconds = wait(
        editor,
        lambda: all(f.loader.active for f in (csv, test, owner)) and settled(editor),
    )
    for file in (csv, test):
        file.references.configure(ReferenceSettings(roots=(str(root),)))
    wait(editor, lambda: settled(editor))
    image, audio = (
        view(owner, "images", ArrayLayout.IMAGE),
        view(owner, "audio", ArrayLayout.AUDIO),
    )
    mapping_seconds = wait(
        editor, lambda: all(f.loader.active for f in (image, audio)) and settled(editor)
    )
    for file in (image, audio):
        file.editor.request(Sort(("label",)))
    wait(editor, lambda: settled(editor))
    owner.arrays.set_retention(1024 * 1024)
    audio.audio.settings = replace(audio.audio.settings, array_sample_rate=8000)
    records(editor, image)
    image.images.jobs.request_window(
        ImageWindow(width=16, height=12), ImageDisplay(), image.arrays.store
    )
    records(editor, audio)
    audio.audio.jobs.request_window(AudioRange(0, 32), audio.arrays.store)
    for file in (csv, image, audio):
        file.text.jobs.settings = replace(
            file.text.jobs.settings,
            column="caption",
            scope=TextScope(CorpusMode.COLLECTION),
        )
    editor.poll()
    for file in (csv, image, audio):
        file.text.jobs.request_document()
    wait(editor, lambda: settled(editor))
    for file in (csv, image, audio):
        file.text.jobs.request_profile()
    wait(editor, lambda: settled(editor))
    assert image.images.jobs.active and image.images.jobs.active.pixel(0, 0) == (
        80,
        20,
        30,
    )
    assert (
        audio.audio.jobs.active and audio.audio.jobs.active.locator.origin.row_id == 1
    )
    assert (
        audio.text.jobs.active
        and audio.text.jobs.active.document.text == "array b e\u0301"
    )
    text_recipe = TextComparisonSettings(
        tuple(
            TextComparisonSource(
                f.identity,
                "caption",
                TextSource.INLINE,
                scope=TextScope(CorpusMode.COLLECTION),
            )
            for f in (csv, test, audio)
        )
    )
    image_recipe = ImageComparisonSettings(
        tuple(
            ImageComparisonSource(
                f.identity, ImageProfileSettings("images" if f is image else "image")
            )
            for f in (csv, test, image)
        ),
        bins=8,
    )
    audio_recipe = AudioComparisonSettings(
        tuple(
            AudioComparisonSource(
                f.identity,
                AudioCollectionSettings(
                    "audio",
                    mode=AudioProfileMode.SIGNAL,
                    array_sample_rate=8000 if f is audio else None,
                ),
            )
            for f in (csv, test, audio)
        ),
        bins=8,
    )
    editor.poll()
    editor.compare.text.draft = text_recipe
    editor.compare.images.draft = image_recipe
    editor.compare.audio.draft = audio_recipe
    for controller in (
        editor.compare.text,
        editor.compare.images,
        editor.compare.audio,
    ):
        controller.prepare()
    comparison_seconds = wait(
        editor,
        lambda: all(
            j.active is not None
            for j in (
                editor.compare.text.jobs,
                editor.compare.images.jobs,
                editor.compare.audio.jobs,
            )
        ),
    )
    prepared = (
        editor.compare.text.jobs.active,
        editor.compare.images.jobs.active,
        editor.compare.audio.jobs.active,
    )
    assert all(prepared)
    prepared_bytes = sum(
        result.retained_bytes for result in prepared if result is not None
    )
    for file in (csv, image, audio):
        assert file.text.jobs.profile
        prepared_bytes += file.text.jobs.profile.retained_bytes
    prepared_bytes += (
        image.images.jobs.active.retained_bytes + audio.audio.jobs.active.retained_bytes
    )
    assert prepared_bytes < 16 * 1024 * 1024
    array_profile = editor.compare.audio.jobs.active
    assert array_profile and array_profile.profiles[2].records["row_id"].to_list() == [
        1,
        2,
        0,
    ]
    assert array_profile.profiles[2].records["duration"].to_list() == [6, 6, 6]
    store = owner.arrays.store
    catalog = owner.arrays.catalog
    assert catalog and catalog.member("audio").container_bytes > store.limit
    disk_before_close = store.stored_bytes
    assert disk_before_close < store.limit
    files = (csv, test, owner, image, audio)
    stores = (store, *(f.images.jobs.store for f in files))
    directories = tuple(
        s.temporary_path for s in stores if s.temporary_path is not None
    )
    owner.record_views.close_view(image.identity)
    wait(editor, lambda: editor.compare.images.jobs.active is None)
    assert editor.compare.audio.jobs.active is array_profile and not store.stop.is_set()
    for file in (owner, csv, test):
        editor.close_file(file.identity)
    close_seconds = wait(editor, lambda: editor.workers.pending == 0)
    assert all(not path.exists() for path in directories)
    assert all(s.stored_bytes == 0 for s in stores)
    assert all(
        f.closed
        and f.loader.active is None
        and f.images.jobs.active is None
        and f.audio.jobs.active is None
        and f.text.jobs.active is None
        and f.text.jobs.profile is None
        for f in files
    )
    assert editor.playback.snapshot.request is None and not editor.playback.devices.busy
    assert editor.playback.snapshot.cpu_bytes == 0
    assert "sounddevice" not in sys.modules and "torch" not in sys.modules
    return {
        "load_seconds": load_seconds,
        "mapping_seconds": mapping_seconds,
        "comparison_seconds": comparison_seconds,
        "prepared_bytes": prepared_bytes,
        "array_member_bytes": catalog.member("audio").container_bytes,
        "array_extractions": store.extractions,
        "disk_before_close": disk_before_close,
        "disk_after_close": store.stored_bytes,
        "close_seconds": close_seconds,
        "removed_directories": len(directories),
        "closed_files_and_views": len(files),
        "playback_bytes_after_close": editor.playback.snapshot.cpu_bytes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    with TemporaryDirectory(prefix="datelier-mixed-sessions-") as temporary:
        root = Path(temporary)
        fixtures = make_multimodal(root)
        with np.load(fixtures.arrays) as archive:
            payloads = {key: archive[key].copy() for key in archive.files}
        payloads["audio"] = np.tile(payloads["audio"], (1, 6, 1))
        np.savez_compressed(fixtures.arrays, **payloads)
        before = {
            p: hashlib.sha256(p.read_bytes()).hexdigest() for p in fixtures.sources
        }
        del payloads
        editor = EditorController()
        try:
            cycles = [cycle(editor, root) for _ in range(6)]
        finally:
            editor.close()
        assert editor.playback.snapshot.cpu_bytes == 0
        assert all(
            hashlib.sha256(p.read_bytes()).hexdigest() == value
            for p, value in before.items()
        )
    peak = (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - baseline) / 1024
    assert peak < 128
    report = {
        "cycles": cycles,
        "peak_rss_increase_mb": peak,
        "source_preserved": True,
        "optional_runtimes_imported": False,
        "editor_closed": editor.closed,
        "gpu_measurement": "pending native mixed workflow",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
