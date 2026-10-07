"""Native audio mappings, scalar legends/links and fresh-process idle restoration."""

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import soundfile as sf
from audio_smoke_controls import NativeControls
from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.audio.comparison_view import AudioComparisonView
from datelier.gui.editor_session import EditorSession
from datelier.gui.layout import configure_layout
from datelier.gui.tabs import EditorTabs
from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
)
from datelier.inspection.audio.collections.settings import AudioProfileMode
from datelier.inspection.audio.playback.controller import PlaybackPhase
from datelier.inspection.references.types import ReferenceSettings
from datelier.pipeline.operations import Sort


def fixtures(root: Path) -> None:
    for name, seconds, rate, amplitude in (
        ("short", 1, 8000, 0.25),
        ("mid", 2, 8000, 0.5),
        ("long", 3, 12000, 0.75),
    ):
        values = amplitude * np.sin(2 * np.pi * 500 * np.arange(seconds * rate) / rate)
        sf.write(
            root / f"{name}.wav",
            np.stack((values, -values), axis=1),
            rate,
            subtype="DOUBLE",
        )
    (root / "train.csv").write_text("clip,label\nshort.wav,a\nmid.wav,z\n")
    (root / "test.csv").write_text("sound,label\nlong.wav,z\nshort.wav,a\nmid.wav,b\n")
    waves = np.empty((3, 8000, 2), dtype=np.float32)
    waves[:, :, 0] = np.array([0.5, 0.25, 0.75])[:, None]
    waves[:, :, 1] = -waves[:, :, 0]
    np.savez_compressed(root / "waves.npz", waves=waves, labels=np.array([3, 1, 2]))


def layout(
    params: hello_imgui.RunnerParams, callbacks: dict[str, Callable[[], None]]
) -> None:
    # Acceptance uses a large existing dockspace; no production layout mutation.
    configure_layout(params, callbacks)
    params.docking_params.docking_splits = []
    for window in params.docking_params.dockable_windows:
        window.dock_space_name = "MainDockSpace"


def run(root: Path, output: Path, restore: bool, array: bool) -> dict[str, object]:
    native = NativeControls()
    view = AudioComparisonView()
    second_name = (
        f"waves.npz waves · {ArrayLayout.AUDIO} · axis 0" if array else "test.csv "
    )
    actions = (
        [
            "Prepare saved array records",
            "idle",
            "Prepare audio comparison",
            "ready",
            "Distributions",
            "chart",
            "finish",
        ]
        if restore and array
        else [
            "idle",
            "Prepare audio comparison",
            "ready",
            "Distributions",
            "chart",
            "finish",
        ]
        if restore
        else [
            "Audio",
            "New audio comparison",
            "Audio mappings and scopes",
            "Include audio train.csv ",
            "Compared audio statistics>1",
            f"Include audio {second_name}",
            "Compared audio statistics>1",
            *(("Compared sample rate (Hz; 0 = unknown)=8000",) if array else ()),
            "Common audio bins=2",
            "Audio mappings and scopes",
            "Prepare audio comparison",
            "ready",
            "chart",
            "Compare audio proportions",
            "Audio selection source>1",
            f"Audio metric bin>{0 if array else 1}",
            "Select matching audio rows",
            "selected",
            "metric",
            "chart",
            "Statistics",
            "statistics",
            "Records",
            "records",
            f"{1 if array else 2}##Audio comparison record",
            "record",
            "finish",
        ]
    )
    stage = action = entered = keyboard = 0
    report: dict[str, object] = {"restore": restore, "array": array}
    keys: list[tuple[imgui.Key, bool]] = []

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, action, entered, keyboard, keys
        params = hello_imgui.get_runner_params()
        if action < len(actions) and ">" in actions[action]:
            imgui.get_io().config_flags |= imgui.ConfigFlags_.nav_enable_keyboard
        else:
            imgui.get_io().config_flags &= ~imgui.ConfigFlags_.nav_enable_keyboard
        if stage == 0:
            if not restore:
                editor.opening.request(
                    (root / "train.csv", root / ("waves.npz" if array else "test.csv")),
                    editor.active_id,
                )
            stage = 1
        if stage == 1:
            if (
                len(editor.files) != 2
                or editor.workspace_jobs.busy
                or any(f.loader.active is None for f in editor.files)
            ):
                return
            if array and not restore:
                owner = editor.files[1]
                if owner.arrays.catalog is None:
                    return
                owner.record_views.open_array(
                    owner,
                    ArrayRecordMapping(
                        "waves",
                        layout=ArrayLayout.AUDIO,
                        display_axes=(1,),
                        channel_axis=2,
                        supporting=(SupportingArray("labels", "label"),),
                    ),
                )
            stage = 2
        if stage == 2:
            second = editor.files[1].record_views.active(editor.files[1])
            if second.loader.active is None:
                if restore and array and second.deferred is not None:
                    params.docking_params.focus_dockable_window("Table preview")
                    if actions[
                        action
                    ] == "Prepare saved array records" and native.advance(
                        "Prepare saved array records", evidence.frames
                    ):
                        action, entered = action + 1, evidence.frames
                return
            for file in editor.file_sessions:
                if file.loader.active is None:
                    continue
                if file.loader.active.imported.array_catalog is not None:
                    continue
                if file.references.settings.roots != (str(root),):
                    file.references.configure(ReferenceSettings(roots=(str(root),)))
                    return
                if (
                    file.references.busy
                    or file.references.source != file.loader.active.dataset.source.path
                    or file.references.index is None
                ):
                    return
            if not restore:
                second.editor.request(Sort(("label",)))
            params.docking_params.focus_dockable_window("Compare files")
            stage, entered = 3, evidence.frames
        second = editor.files[1].record_views.active(editor.files[1])
        if stage == 3:
            if second.editor.busy:
                return
            if (
                second.loader.active is not None
                and second.loader.active.dataset.row_ids.to_list() != [1, 2, 0]
            ):
                if not restore or not array:
                    raise AssertionError(second.loader.active.dataset.row_ids)
            stage = 4
        if action == len(actions):
            if restore or editor.workspace_jobs.saved is not None:
                params.app_shall_exit = True
            return
        target, age = actions[action], evidence.frames - entered
        jobs, state = editor.audio_comparison_jobs, editor.playback.snapshot
        assert state.phase == PlaybackPhase.IDLE and state.request is None
        assert not editor.playback.devices.busy
        if target == "Prepare saved array records":
            # The deferred record table owns this explicit recovery command.
            params.docking_params.focus_dockable_window("Table preview")
        if target in (
            "idle",
            "ready",
            "chart",
            "selected",
            "statistics",
            "records",
            "record",
            "metric",
            "finish",
        ):
            if age < 14:
                return
            result = jobs.active
            if target == "idle":
                assert (
                    restore and jobs.started == 0 and not jobs.busy and result is None
                )
                assert (
                    editor.comparison_tab == "Audio"
                    and editor.audio_comparison_view.metric == "RMS"
                )
                assert not editor.audio_comparison_view.proportions
                assert editor.audio_comparisons[0].bins == 2 and all(
                    s.profile.mode == AudioProfileMode.SIGNAL
                    for s in editor.audio_comparisons[0].sources
                )
                report["idle_saved_controls"] = True
                params.docking_params.focus_dockable_window("Compare files")
            elif target == "ready":
                if result is None:
                    if age > 180 and not jobs.busy:
                        raise AssertionError(
                            (jobs.message, jobs.started, editor.audio_comparisons)
                        )
                    return
                assert [p.ready for p in result.profiles] == [2, 3]
                assert result.profiles[1].records["row_id"].to_list() == [1, 2, 0]
                curve = next(c for c in result.curves if c.metric.name == "Duration")
                assert curve.edges.tolist() == ([1, 1.5, 2] if array else [1, 2, 3])
                assert curve.counts[0] is not None and curve.counts[0].tolist() == [
                    0,
                    1,
                    1,
                    0,
                ]
                assert curve.counts[1] is not None and curve.counts[1].tolist() == (
                    [0, 3, 0, 0] if array else [0, 1, 2, 0]
                )
                if array:
                    assert {
                        c.metric.family for c in result.curves if c.metric.name == "RMS"
                    } == {"full-scale amplitude", "array amplitude · float32"}
                report["native_mappings_and_exact_scans"] = not restore
                report["comparison_retained_bytes"] = result.retained_bytes
            elif target == "chart":
                if view.plot_frames < 5:
                    return
                if restore:
                    assert editor.audio_comparison_view.metric == "RMS"
                report["native_distributions_and_legends"] = True
            elif target == "selected":
                if not second.selection.row_ids:
                    return
                assert second.selection.row_ids == ({0, 1, 2} if array else {0, 2})
                assert (
                    not editor.files[0].selection.row_ids
                    and editor.active is editor.files[1]
                )
                report["source_scoped_selection"] = True
            elif target in ("statistics", "records"):
                if view.rendered_rows < 3:
                    return
                report[f"native_{target}"] = True
            elif target == "record":
                if second.audio.jobs.metadata is None:
                    return
                locator, metadata = second.audio.jobs.metadata
                assert locator.origin.row_id == (1 if array else 2)
                assert (
                    second.exploration.active_tab == "Inspect"
                    and metadata.sample_rate == 8000
                ), (second.exploration.active_tab, metadata, second.focus_inspect)
                assert second.loader.active is not None
                assert second.loader.active.dataset.table["label"][
                    0 if array else 1
                ] == (1 if array else "b")
                assert (
                    second.audio.jobs.active is None
                    and second.audio.jobs.profile is None
                )
                report["native_supporting_record_link"] = True
            elif target == "metric":
                assert result is not None
                desired = next(
                    i
                    for i, c in enumerate(result.curves)
                    if c.metric.name == "RMS"
                    and c.metric.channel == 1
                    and c.metric.family
                    == (
                        "array amplitude · float32" if array else "full-scale amplitude"
                    )
                )
                actions[action] = f"Compared audio metric>{desired}"
                return
            elif target == "finish":
                assert (
                    result is not None and editor.audio_comparison_view.metric == "RMS"
                ), editor.audio_comparison_view
                assert (
                    editor.audio_comparison_view.channel == 1
                    and not editor.audio_comparison_view.proportions
                )
                report.update(frames=evidence.frames)
                if not restore:
                    editor.save_workspace(root / "session.datelier.json")
            action, entered = action + 1, evidence.frames
            return
        if age < 14 and not keys:
            return
        if ">" in target:
            imgui.get_io().config_flags |= imgui.ConfigFlags_.nav_enable_keyboard
            label, index = target.rsplit(">", 1)
            if not keys:
                if native.advance(label, evidence.frames):
                    keys = [(imgui.Key.home, True), (imgui.Key.home, False)]
                    keys += [
                        (key, down)
                        for _ in range(int(index))
                        for key, down in (
                            (imgui.Key.down_arrow, True),
                            (imgui.Key.down_arrow, False),
                        )
                    ]
                    keys += [(imgui.Key.enter, True), (imgui.Key.enter, False)]
                    keyboard, entered = 0, evidence.frames
            elif age > 4:
                key, down = keys[keyboard]
                imgui.get_io().add_key_event(key, down)
                keyboard, entered = keyboard + 1, evidence.frames
                if keyboard == len(keys):
                    keys = []
                    action += 1
            return
        if native.advance(target, evidence.frames):
            action, entered = action + 1, evidence.frames

    def safe_frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        try:
            frame(editor, tabs, evidence)
        except Exception as error:
            report["failure"] = repr(error)
            report["input_positions"] = {
                key: native.points.get(key)
                for key in (
                    "Distributions",
                    "Compared audio metric",
                    "Audio result source",
                )
            }
            hello_imgui.get_runner_params().app_shall_exit = True

    with (
        native.patched(),
        patch("datelier.gui.app.configure_layout", layout),
        patch("datelier.gui.app.AudioComparisonView", lambda: view),
    ):
        evidence = run_gui(
            initial_workspace=root / "session.datelier.json" if restore else None,
            preferences_path=root / "preferences.json",
            smoke_frames=2200,
            on_editor_frame=safe_frame,
        )
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / "latest-native.png"
    )
    assert "failure" not in report, report
    assert action == len(actions), (stage, action, actions[action], native.points)
    p95 = float(np.percentile(evidence.frame_intervals_ms[10:], 95))
    assert p95 < 33, p95
    report.update(frames=evidence.frames, frame_p95_ms=p95)
    assert "sounddevice" not in sys.modules, "Comparison imported playback IO"
    pixels = hello_imgui.final_app_window_screenshot()
    assert pixels.size
    prefix = "audio-comparison-array" if array else "audio-comparison-file"
    Image.fromarray(pixels).save(
        output / f"{prefix}{'-restored' if restore else ''}.png"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--array", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.root is not None:
        print(json.dumps(run(args.root, args.output, args.restore, args.array)))
        return
    with TemporaryDirectory(prefix="datelier-audio-compare-native-") as temporary:
        root = Path(temporary)
        fixtures(root)
        paths = (
            tuple(root.glob("*.wav"))
            + tuple(root.glob("*.csv"))
            + tuple(root.glob("*.npz"))
        )
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        saved = run(root, args.output, False, args.array)
        completed = subprocess.run(
            [
                sys.executable,
                __file__,
                "--root",
                str(root),
                "--output",
                str(args.output),
                "--restore",
                *(("--array",) if args.array else ()),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert completed.returncode == 0, completed.stderr
        restored = json.loads(completed.stdout.strip().splitlines()[-1])
        assert all(
            hashlib.sha256(path.read_bytes()).hexdigest() == original
            for path, original in before.items()
        )
        report = {"save": saved, "restore": restored, "source_preserved": True}
        prefix = "audio-comparison-array" if args.array else "audio-comparison-file"
        (args.output / f"{prefix}-native.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
