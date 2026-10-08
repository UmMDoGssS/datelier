"""Hidden native mixed modality commands, GPU ownership and independent restore."""

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
from audio_smoke_controls import NativeControls
from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.feasibility.multimodal import make_multimodal
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.file_session import FileSession
from datelier.gui.layout import configure_layout
from datelier.gui.tabs import EditorTabs
from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
)
from datelier.inspection.audio.collections.settings import (
    AudioCollectionSettings,
    AudioProfileMode,
)
from datelier.inspection.audio.comparisons.settings import (
    AudioComparisonSettings,
    AudioComparisonSource,
)
from datelier.inspection.audio.view_types import AudioViewKind, SpectralView
from datelier.inspection.images.comparisons.settings import (
    ImageComparisonSettings,
    ImageComparisonSource,
)
from datelier.inspection.images.profile_types import ImageProfileSettings
from datelier.inspection.records.types import RecordMode
from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.text.comparisons.settings import (
    TextComparisonSettings,
    TextComparisonSource,
)
from datelier.inspection.text.types import CorpusMode, TextScope, TextSource
from datelier.io.types import ArrayOptions
from datelier.pipeline.operations import Sort


def layout(
    params: hello_imgui.RunnerParams, callbacks: dict[str, Callable[[], None]]
) -> None:
    configure_layout(params, callbacks)
    params.app_window_params.hidden = True
    params.app_window_params.window_geometry.size = (1400, 1000)
    params.docking_params.docking_splits = []
    for window in params.docking_params.dockable_windows:
        window.dock_space_name = "MainDockSpace"


def mapped(owner: FileSession, member: str, layout: ArrayLayout) -> FileSession:
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


def mapping(file: FileSession) -> ArrayRecordMapping:
    value = (
        file.loader.active.imported.options
        if file.loader.active
        else file.deferred.file.recipe.options
        if file.deferred and file.deferred.file.recipe
        else None
    )
    assert isinstance(value, ArrayOptions) and value.mapping is not None
    return value.mapping


def focus(
    editor: EditorSession,
    owner: FileSession,
    file: FileSession,
    column: str | None,
    row: int,
) -> None:
    assert file.loader.active
    owner.record_views.active_id = file.identity if file is not owner else None
    editor.activate(owner.identity)
    file.selection.choose(file.loader.active.dataset.revision, (row,))
    file.inspect.settings = replace(
        file.inspect.settings,
        mode=RecordMode.SELECTION,
        primary=column,
        supporting=("caption", "label"),
        gallery=False,
        focus=0,
    )
    file.exploration.tab = "Inspect"
    file.focus_inspect = owner.focus_inspect = True
    hello_imgui.get_runner_params().docking_params.focus_dockable_window("Explore")


def run(root: Path, output: Path, restore: bool) -> dict[str, object]:
    native = NativeControls()
    report: dict[str, object] = {"restore": restore, "hidden": True}
    actions = [
        "Text corpora",
        "Prepare text comparison",
        "text-ready",
        "Images",
        "Prepare image comparison",
        "image-ready",
        "Audio",
        "Prepare audio comparison",
        "audio-ready",
        "text-inspect",
        "Inspect text tokens",
        "tokens-ready",
        "image-inspect",
        "Fit image",
        "1:1 pixels",
        "pixels-ready",
        "audio-inspect",
        "Time start (s)=0.25",
        "Time end (s)=0.75",
        "Sample channel (1-based)=2",
        "Spectrogram",
        "spectrum-ready",
        "Mel spectrogram",
        "mel-ready",
        "Profile selected range",
        "profile-ready",
        "save",
    ]
    stage = action = entered = 0
    observed: list[FileSession] = []
    owner: FileSession | None = None
    image: FileSession | None = None
    audio: FileSession | None = None
    peak_gpu = peak_cpu = 0
    timings: dict[str, list[float]] = {}

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, action, entered, owner, image, audio, peak_gpu, peak_cpu
        params = hello_imgui.get_runner_params()
        if evidence.frame_intervals_ms:
            key = (
                actions[action] if stage == 3 and action < len(actions) else "load/save"
            )
            timings.setdefault(key, []).append(evidence.frame_intervals_ms[-1])
        assert "torch" not in sys.modules and "sounddevice" not in sys.modules
        assert editor.playback.snapshot.request is None
        files = editor.files
        if stage == 0:
            observed.append(editor.active)
            if not restore:
                editor.opening.request(
                    tuple(
                        root / name for name in ("train.csv", "test.csv", "records.npz")
                    ),
                    editor.active_id,
                )
            stage = 1
        if stage == 1:
            if (
                len(files) != 3
                or editor.workspace_jobs.busy
                or any(f.loader.active is None for f in files)
            ):
                return
            owner = files[2]
            if owner.arrays.catalog is None:
                return
            if not restore:
                image, audio = (
                    mapped(owner, "images", ArrayLayout.IMAGE),
                    mapped(owner, "audio", ArrayLayout.AUDIO),
                )
            else:
                image = next(
                    f for f in owner.record_views.files if mapping(f).member == "images"
                )
                audio = next(
                    f for f in owner.record_views.files if mapping(f).member == "audio"
                )
                assert (
                    image.deferred
                    and audio.deferred
                    and owner.arrays.store.extractions == 0
                )
                assert all(
                    j.started == 0 and j.active is None
                    for j in (
                        editor.text_comparison_jobs,
                        editor.image_comparison_jobs,
                        editor.audio_comparison_jobs,
                    )
                )
                assert not editor.playback.devices.busy
                report["idle_restore"] = True
            stage, entered = 2, evidence.frames
        assert owner is not None and image is not None and audio is not None
        if stage == 2:
            for file in (image, audio):
                if file.loader.active is None:
                    if restore and file.deferred:
                        editor.activate(owner.identity)
                        owner.record_views.active_id = file.identity
                        params.docking_params.focus_dockable_window("Table preview")
                        native.advance("Prepare saved array records", evidence.frames)
                    return
            if any(f.editor.busy or f.record_views.pending for f in files):
                return
            for file in files[:2]:
                if file.references.settings.roots != (str(root),):
                    file.references.configure(ReferenceSettings(roots=(str(root),)))
                    return
                if file.references.busy or file.references.index is None:
                    return
            if not restore:
                for file in (image, audio):
                    file.editor.request(Sort(("label",)))
                audio.audio.settings = replace(
                    audio.audio.settings,
                    array_sample_rate=8000,
                    view=replace(
                        audio.audio.settings.view, fft=256, hop=64, mel_bands=32
                    ),
                )
                editor.text_comparisons = (
                    TextComparisonSettings(
                        tuple(
                            TextComparisonSource(
                                f.identity,
                                "caption",
                                TextSource.INLINE,
                                scope=TextScope(CorpusMode.COLLECTION),
                            )
                            for f in (*files[:2], audio)
                        )
                    ),
                )
                editor.image_comparisons = (
                    ImageComparisonSettings(
                        tuple(
                            ImageComparisonSource(
                                f.identity,
                                ImageProfileSettings(
                                    "images" if f is image else "image"
                                ),
                            )
                            for f in (*files[:2], image)
                        ),
                        bins=8,
                    ),
                )
                editor.audio_comparisons = (
                    AudioComparisonSettings(
                        tuple(
                            AudioComparisonSource(
                                f.identity,
                                AudioCollectionSettings(
                                    "audio",
                                    mode=AudioProfileMode.SIGNAL,
                                    array_sample_rate=8000 if f is audio else None,
                                ),
                            )
                            for f in (*files[:2], audio)
                        ),
                        bins=8,
                    ),
                )
            owner.arrays.set_retention(1024 * 1024)
            editor.comparison_tab = "Text corpora"
            params.docking_params.focus_dockable_window("Compare files")
            observed.extend(editor.file_sessions)
            stage, entered = 3, evidence.frames
            return
        if any(f.editor.busy for f in (image, audio)):
            return
        for file in (image, audio):
            assert (
                file.loader.active
                and file.loader.active.dataset.row_ids.to_list() == [1, 2, 0]
            )
        gpu = sum(
            f.images.canvas.retained_bytes
            + f.audio.canvas.retained_bytes
            + f.reference_view.textures.retained_bytes
            for f in editor.file_sessions
        )
        cpu = sum(
            result.retained_bytes
            for result in (
                editor.text_comparison_jobs.active,
                editor.image_comparison_jobs.active,
                editor.audio_comparison_jobs.active,
            )
            if result is not None
        )
        cpu += sum(
            (f.images.jobs.active.retained_bytes if f.images.jobs.active else 0)
            + (f.audio.signal.active.retained_bytes if f.audio.signal.active else 0)
            for f in editor.file_sessions
        )
        peak_gpu, peak_cpu = max(peak_gpu, gpu), max(peak_cpu, cpu)
        assert peak_gpu < 32 * 1024 * 1024 and peak_cpu < 16 * 1024 * 1024
        if action == len(actions):
            if restore or editor.workspace_jobs.saved is not None:
                params.app_shall_exit = True
            return
        target, age = actions[action], evidence.frames - entered
        if target.endswith("-ready") or target.endswith("-inspect") or target == "save":
            if age < 12:
                return
            if target == "text-ready":
                result = editor.text_comparison_jobs.active
                if result is None:
                    return
                assert [p.documents for p in result.profiles] == [2, 3, 3]
                report["text_documents"] = [2, 3, 3]
            elif target == "image-ready":
                result = editor.image_comparison_jobs.active
                if result is None:
                    return
                assert [p.ready for p in result.profiles] == [2, 3, 3]
                report["image_records"] = [2, 3, 3]
            elif target == "audio-ready":
                result = editor.audio_comparison_jobs.active
                if result is None:
                    return
                assert [p.ready for p in result.profiles] == [2, 3, 3]
                assert result.profiles[2].records["row_id"].to_list() == [1, 2, 0]
                report["audio_records"] = [2, 3, 3]
            elif target == "text-inspect":
                focus(editor, files[0], files[0], "caption", 0)
            elif target == "tokens-ready":
                result = files[0].text.jobs.active
                if result is None:
                    return
                assert (
                    result.document.text == "alpha e\u0301 中🙂"
                    and result.document.origin.row_id == 0
                )
                assert files[0].text.shown > 0
                report["text_tokens"] = result.count
            elif target == "image-inspect":
                focus(editor, owner, image, None, 1)
            elif target == "pixels-ready":
                result = image.images.jobs.active
                if result is None or image.images.canvas.uploads == 0:
                    return
                assert (
                    result.pixel(0, 0) == (80, 20, 30)
                    and result.locator.origin.row_id == 1
                )
                assert image.images.settings.viewport.zoom == 1
                report["original_pixel"] = [80, 20, 30]
            elif target == "audio-inspect":
                result = editor.audio_comparison_jobs.active
                assert result is not None
                editor.open_audio_comparison_record(result, 2, 0)
                params.docking_params.focus_dockable_window("Explore")
            elif target in ("spectrum-ready", "mel-ready"):
                result = audio.audio.signal.active
                kind = (
                    AudioViewKind.MEL
                    if target == "mel-ready"
                    else AudioViewKind.SPECTROGRAM
                )
                if result is None or result.settings.mode != kind:
                    return
                assert (
                    result.range.start == 2000
                    and result.range.stop == 6000
                    and result.channel == 1
                )
                assert (
                    result.metadata.sample_rate == 8000
                    and result.locator.origin.row_id == 1
                )
                assert isinstance(result, SpectralView)
                peak = float(result.frequencies[int(result.power[:, 0].argmax())])
                assert 420 < peak < 580 if kind == AudioViewKind.MEL else peak == 500
                report[target] = {
                    "range": [2000, 6000],
                    "rate": 8000,
                    "channel": 2,
                    "peak_hz": peak,
                }
            elif target == "profile-ready":
                result = audio.audio.jobs.profile
                if result is None:
                    return
                assert result.range.start == 2000 and result.range.stop == 6000
                assert result.locator.origin.row_id == 1
                report["explicit_audio_profile"] = True
            elif target == "save" and not restore:
                editor.save_workspace(
                    root / "session.datelier.json",
                    layout=imgui.save_ini_settings_to_memory(),
                    overwrite=True,
                )
            action, entered = action + 1, evidence.frames
            return
        if age > 300:
            raise AssertionError(
                f"Native input stalled: {target}; point={native.points.get(target)}, "
                f"clip={native.clips.get(target)}; phase={native.phase}"
            )
        if native.advance(target, evidence.frames):
            action, entered = action + 1, evidence.frames

    def safe_frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        try:
            frame(editor, tabs, evidence)
        except Exception as error:
            report["failure"] = repr(error)
            report["action"] = (
                actions[action] if action < len(actions) else "completion"
            )
            hello_imgui.get_runner_params().app_shall_exit = True

    with native.patched(), patch("datelier.gui.app.configure_layout", layout):
        evidence = run_gui(
            initial_workspace=root / "session.datelier.json" if restore else None,
            preferences_path=root / "preferences.json",
            smoke_frames=1800,
            on_editor_frame=safe_frame,
        )
    screenshot = hello_imgui.final_app_window_screenshot()
    assert screenshot is not None
    Image.fromarray(screenshot).save(
        output / ("multimodal-restored.png" if restore else "multimodal.png")
    )
    assert "failure" not in report, report
    assert action == len(actions), (actions[action], report)
    assert all(
        f.closed
        and f.audio.canvas.retained_bytes == 0
        and f.images.canvas.retained_bytes == 0
        and f.arrays.store.stored_bytes == 0
        for f in observed
    )
    p95 = float(np.percentile(evidence.frame_intervals_ms[10:], 95))
    report.update(
        {
            "frames": evidence.frames,
            "frame_p95_ms": p95,
            "peak_prepared_cpu_bytes": peak_cpu,
            "peak_gpu_bytes": peak_gpu,
            "closed_gpu_and_array_bytes": 0,
            "no_playback_or_training": True,
            "stage_frame_p95_ms": {
                key: float(np.percentile(values, 95)) for key, values in timings.items()
            },
        }
    )
    assert p95 < 33, report
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.restore:
        assert args.root is not None
        report = run(args.root, args.output, True)
        (args.output / "multimodal-restored.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))
        return
    with TemporaryDirectory(prefix="datelier-mixed-native-") as temporary:
        root = args.root or Path(temporary)
        fixtures = make_multimodal(root)
        before = {
            p: hashlib.sha256(p.read_bytes()).hexdigest() for p in fixtures.sources
        }
        report = run(root, args.output, False)
        subprocess.run(
            [
                sys.executable,
                __file__,
                "--output",
                str(args.output),
                "--root",
                str(root),
                "--restore",
            ],
            check=True,
        )
        assert all(
            hashlib.sha256(p.read_bytes()).hexdigest() == value
            for p, value in before.items()
        )
        report["source_preserved"] = True
        (args.output / "multimodal-native.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
