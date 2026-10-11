"""Native explicit audio comparisons, metrics, resize and source-owned Inspect."""

import json
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import soundfile as sf
from imgui_bundle import hello_imgui, imgui
from rebuild_input import NativeInput

from datelier.application.comparisons import ComparisonFamily
from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.audio.collections.settings import AudioProfileMode
from datelier.inspection.audio.playback.controller import PlaybackPhase
from datelier.pipeline.operations import Sort

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from audio_playback_fixtures import Devices  # noqa: E402


def main() -> None:
    with TemporaryDirectory(prefix="datelier-audio-compare-") as directory:
        root = Path(directory)
        first = root / "train.csv"
        second = root / "test.csv"
        for name, frames in (("short", 8000), ("long", 16000)):
            sf.write(
                root / f"{name}.wav", np.full((frames, 2), 0.25), 8000, subtype="DOUBLE"
            )
        first.write_text("audio,label\nlong.wav,z\nshort.wav,a\n")
        second.write_text("path\nshort.wav\nlong.wav\n")
        originals = first.read_bytes(), second.read_bytes()
        native = NativeInput()
        devices = Devices()
        stage = entered = 0
        done = False
        first_id = ""

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, done, first_id
            model = editor.compare.audio
            age = evidence.frames - entered
            if evidence.frames > 750:
                raise AssertionError(
                    (stage, model.message, model.jobs.selection_message)
                )
            if native.advance(evidence.frames):
                return
            suffix = None
            if stage == 0 and editor.active.inspection:
                first_id = editor.active_id
                editor.active.editor.request(Sort(("label",)))
                editor.new_file(second)
                stage, entered = 1, evidence.frames
            elif (
                stage == 1
                and len(editor.files) == 2
                and all(
                    f.inspection and not f.editor.busy and not f.references.busy
                    for f in editor.files
                )
            ):
                editor.choose_route("Compare files")
                editor.compare.tab = ComparisonFamily.AUDIO
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 5:
                suffix = ("contributors", "files", "open")
            elif stage == 3 and age > 5:
                suffix = ("files", "list", "bulk")
            elif stage == 4 and age > 5:
                assert len(model.draft.sources) == 2 and model.jobs.started == 0
                imgui.get_io().add_key_event(imgui.Key.escape, True)
                stage, entered = 5, evidence.frames
            elif stage == 5:
                imgui.get_io().add_key_event(imgui.Key.escape, False)
                model.draft = replace(
                    model.draft,
                    bins=2,
                    sources=tuple(
                        replace(
                            s, profile=replace(s.profile, mode=AudioProfileMode.SIGNAL)
                        )
                        for s in model.draft.sources
                    ),
                )
                stage, entered = 6, evidence.frames
            elif stage == 6 and age > 5:
                suffix = ("recipe-controls", "apply", "run")
            elif stage == 7 and model.active and age > 5:
                assert [p.ready for p in model.active.profiles] == [2, 2]
                assert all(p.channel_records.height == 4 for p in model.active.profiles)
                assert model.curve and model.curve.metric.name == "Duration"
                assert (
                    editor.navigation.comparing and not editor.playback.snapshot.request
                )
                suffix = ("audio-comparison-viewport", "expand")
            elif stage == 8 and age > 5:
                suffix = ("audio-comparison-viewport", "restore")
            elif stage == 9 and age > 5:
                suffix = ("Statistics", "tab")
            elif stage == 10 and age > 5:
                assert model.view.tab == "Statistics"
                rms = next(
                    m for m in model.metrics if m.name == "RMS" and m.channel == 1
                )
                model.view = replace(
                    model.view, metric=rms.name, family=rms.family, channel=rms.channel
                )
                assert len(model.statistics) == 2
                suffix = ("Distributions", "tab")
            elif stage == 11 and age > 5:
                duration = next(m for m in model.metrics if m.name == "Duration")
                model.view = replace(
                    model.view,
                    metric=duration.name,
                    family=duration.family,
                    channel=duration.channel,
                )
                suffix = ("audio-comparison-chart", "canvas")
            elif stage == 12 and editor.current.selection.row_ids:
                assert editor.active_id == first_id and not editor.navigation.comparing
                assert editor.current.selection.row_ids in ({0}, {1})
                editor.choose_route("Compare files")
                model.view = replace(model.view, source=0)
                stage, entered = 13, evidence.frames
            elif stage == 13 and age > 5:
                suffix = ("Records", "tab")
            elif stage == 14 and age > 5:
                suffix = ("records", "open-1")
            elif stage == 15 and editor.current.audio.jobs.metadata:
                assert (
                    editor.current.views.tab == "Inspect"
                    and editor.current.selection.row_ids == {0}
                )
                assert editor.current.audio.jobs.metadata[1].sample_rate == 8000
                assert (
                    editor.playback.snapshot.phase == PlaybackPhase.IDLE
                    and not editor.playback.snapshot.request
                )
                assert (
                    originals == (first.read_bytes(), second.read_bytes())
                    and not devices.devices
                )
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix and native.click(probe, suffix, evidence.frames):
                stage, entered = stage + 1, evidence.frames

        evidence = run_gui(
            initial_path=first, on_probe_frame=frame, playback_factory=devices.create
        )
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_shared_contributors": True,
            "explicit_exact_signal_prepare": True,
            "metric_family_channel_selection": True,
            "distributions_statistics_records": True,
            "expand_restore": True,
            "original_sorted_rows_linked": True,
            "record_open_original_rate": True,
            "source_preserved": True,
            "implicit_profiles_playback": False,
            "output_devices_opened": len(devices.devices),
            "human_listening": "deferred",
        }
        Path("/tmp/datelier-rebuild-audio-comparisons.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
