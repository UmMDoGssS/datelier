"""Native probe-based input gates for the replacement workbench."""

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui
from PIL import Image
from rebuild_input import NativeInput, NativeText

from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.workspace.preferences import Preferences, Theme, save_preferences


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--theme", choices=tuple(Theme), default=Theme.DARK)
    parser.add_argument("--output", type=Path, default=Path("/tmp/datelier-rebuild"))
    args = parser.parse_args()
    with TemporaryDirectory(prefix="datelier-rebuild-") as directory:
        source = Path(directory) / "source.csv"
        rng = np.random.default_rng(71)
        x = rng.normal(size=1200)
        pl.DataFrame(
            {
                "x": x,
                "y": x * 0.8 + rng.normal(size=1200),
                "z": rng.normal(size=1200),
                "label": [f"group {i % 4}" for i in range(1200)],
            }
        ).write_csv(source)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        preferences = Path(directory) / "preferences.json"
        save_preferences(preferences, Preferences(theme=Theme(args.theme)))
        phase = 0
        stage_frame = 0
        start: tuple[float, float] | None = None
        checked: dict[str, object] = {}

        native, text = NativeInput(), NativeText()

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal phase, stage_frame, start
            file = editor.active
            age = evidence.frames - stage_frame
            if evidence.frames > 500:
                raise AssertionError((phase, list(k.path for k in probe.targets)))
            if native.advance(evidence.frames) or text.advance(evidence.frames):
                return
            suffix: tuple[str, ...] | None = None
            if phase == 0 and file.explorer.profiles.active and evidence.frames > 20:
                start = native.find(probe, ("numeric-plot", "resize"))
                assert start
                checked["profiles"] = len(
                    file.explorer.profiles.active.profiles.columns
                )
                native.drag(start, (start[0], start[1] + 35), evidence.frames)
                phase, stage_frame = 1, evidence.frames
            elif phase == 1 and age > 3:
                resized = native.find(probe, ("numeric-plot", "resize"))
                assert resized and start and 25 <= resized[1] - start[1] <= 45
                checked["resize_delta"] = resized[1] - start[1]
                suffix = ("numeric-plot", "expand")
            elif phase == 2 and age > 3:
                suffix = ("numeric-plot", "restore")
            elif phase == 3 and age > 3:
                assert not native.find(probe, ("numeric-plot", "restore"))
                checked["native_expand_restore"] = True
                suffix = ("numeric-plot", "auto")
            elif phase == 4 and age > 3:
                assert file.profiles.height == 0
                suffix = ("Relationships", "tab")
            elif phase == 5 and age > 3:
                assert file.views.tab == "Relationships"
                checked["relationships"] = True
                suffix = ("Correlations", "tab")
            elif phase == 6 and age > 3:
                assert file.views.tab == "Correlations"
                if args.width < 1100:
                    assert not native.find(probe, ("features", "open"))
                    suffix = ("files", "context")
                else:
                    phase, stage_frame = 7, evidence.frames
            elif phase == 7 and age > 3:
                context = imgui.internal.find_window_by_name("Context")
                assert context and context.size.x >= 270
                assert bool(context.dock_id == 0) == (args.width < 1100)
                checked["context_drawer"] = args.width < 1100
                suffix = ("features", "open")
            elif phase == 8 and age > 3:
                suffix = ("features", "list", "search")
            elif phase == 9:
                text.start("y", evidence.frames)
                phase, stage_frame = 10, evidence.frames
            elif phase == 10 and age > 3:
                assert native.find(probe, ("features", "list", "y", "select"))
                assert not native.find(probe, ("features", "list", "x", "select"))
                suffix = ("features", "list", "bulk")
            elif phase == 11 and age > 3:
                assert file.plots.relationship_features == ["y"]
                checked["native_keyboard_filtered_column_selection"] = True
                imgui.get_io().add_key_event(imgui.Key.escape, True)
                phase, stage_frame = 12, evidence.frames
            elif phase == 12:
                imgui.get_io().add_key_event(imgui.Key.escape, False)
                phase, stage_frame = 13, evidence.frames
            elif phase == 13 and age > 3:
                assert not native.find(probe, ("features", "list", "search"))
                assert file.analysis.jobs.latest is None
                assert file.audio.player.snapshot.request is None
                assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
                assert editor.preferences.value.theme == Theme(args.theme)
                checked.update(
                    correlations=True,
                    source_preserved=True,
                    implicit_operations=0,
                    targets=len(probe.targets),
                )
                hello_imgui.get_runner_params().app_shall_exit = True
                phase = 14
            if suffix:
                pixel = native.find(probe, suffix)
                if pixel:
                    native.click_point(pixel, evidence.frames)
                    phase, stage_frame = phase + 1, evidence.frames

        evidence = run_gui(
            source,
            window_size=(args.width, args.height),
            preferences_path=preferences,
            on_probe_frame=frame,
        )
        capture = hello_imgui.final_app_window_screenshot()
        if capture is not None and capture.size:
            Image.fromarray(capture).save(str(args.output) + ".png")
        assert phase == 14, checked
        report = {
            "frames": evidence.frames,
            "frame_p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "size": [args.width, args.height],
            "theme": args.theme,
            **checked,
        }
        Path(str(args.output) + ".json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
