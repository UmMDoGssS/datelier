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

from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=800)
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
        phase = 0
        stage_frame = 0
        start: tuple[float, float] | None = None
        checked: dict[str, object] = {}

        def point(
            probe: GuiProbe, suffix: tuple[str, ...]
        ) -> tuple[float, float] | None:
            return next(
                (
                    value
                    for key, value in probe.targets.items()
                    if key.path[-len(suffix) :] == suffix
                ),
                None,
            )

        def move(pixel: tuple[float, float]) -> None:
            io = imgui.get_io()
            io.mouse_pos = imgui.ImVec2(*pixel)
            io.want_set_mouse_pos = True

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal phase, stage_frame, start
            file = editor.active
            age = evidence.frames - stage_frame
            io = imgui.get_io()
            if evidence.frames > 250:
                raise AssertionError((phase, list(k.path for k in probe.targets)))
            if phase == 0:
                if file.explorer.profiles.active and evidence.frames > 20:
                    start = point(probe, ("numeric-plot", "resize"))
                    assert start
                    checked["profiles"] = len(
                        file.explorer.profiles.active.profiles.columns
                    )
                    move(start)
                    phase, stage_frame = 1, evidence.frames
            elif phase == 1 and age > 3:
                io.add_mouse_button_event(0, True)
                phase, stage_frame = 2, evidence.frames
            elif phase == 2 and age > 3:
                assert start
                move((start[0], start[1] + 35))
                phase, stage_frame = 3, evidence.frames
            elif phase == 3 and age > 3:
                io.add_mouse_button_event(0, False)
                phase, stage_frame = 4, evidence.frames
            elif phase == 4 and age > 3:
                resized = point(probe, ("numeric-plot", "resize"))
                assert resized and start and 25 <= resized[1] - start[1] <= 45
                checked["resize_delta"] = resized[1] - start[1]
                pixel = point(probe, ("Relationships", "tab"))
                assert pixel
                move(pixel)
                phase, stage_frame = 5, evidence.frames
            elif phase == 5 and age > 3:
                io.add_mouse_button_event(0, True)
                phase, stage_frame = 6, evidence.frames
            elif phase == 6 and age > 3:
                io.add_mouse_button_event(0, False)
                phase, stage_frame = 7, evidence.frames
            elif phase == 7 and age > 4:
                assert file.views.tab == "Relationships"
                checked["relationships"] = True
                pixel = point(probe, ("Correlations", "tab"))
                assert pixel
                move(pixel)
                phase, stage_frame = 8, evidence.frames
            elif phase == 8 and age > 3:
                io.add_mouse_button_event(0, True)
                phase, stage_frame = 9, evidence.frames
            elif phase == 9 and age > 3:
                io.add_mouse_button_event(0, False)
                phase, stage_frame = 10, evidence.frames
            elif phase == 10 and age > 5:
                assert file.views.tab == "Correlations"
                assert file.analysis.jobs.latest is None
                assert file.audio.player.snapshot.request is None
                assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
                checked["correlations"] = True
                checked["source_preserved"] = True
                checked["implicit_operations"] = 0
                checked["targets"] = len(probe.targets)
                hello_imgui.get_runner_params().app_shall_exit = True
                phase = 11

        evidence = run_gui(
            source, window_size=(args.width, args.height), on_probe_frame=frame
        )
        capture = hello_imgui.final_app_window_screenshot()
        if capture is not None and capture.size:
            Image.fromarray(capture).save(str(args.output) + ".png")
        assert phase == 11, checked
        report = {
            "frames": evidence.frames,
            "frame_p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "size": [args.width, args.height],
            **checked,
        }
        Path(str(args.output) + ".json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
