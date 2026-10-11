"""Native split resizing remains custom across compact/wide window changes."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui, imgui
from rebuild_input import NativeInput
from rebuild_motion import NativeMotion

from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe


def main() -> None:
    with TemporaryDirectory(prefix="datelier-splitter-") as directory:
        source = Path(directory) / "data.csv"
        source.write_text("x,y\n1.0,2.0\n3.0,4.0\n")
        native, motion = NativeInput(), NativeMotion()
        stage = entered = 0
        original_width = resized_width = 0.0
        done = False

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, original_width, resized_width, done
            window = imgui.internal.find_window_by_name("Source browser")
            assert evidence.frames < 300, (stage, window.size.x if window else None)
            if native.advance(evidence.frames) or motion.advance(evidence.frames):
                return
            age = evidence.frames - entered
            if stage == 0 and editor.current.inspection and evidence.frames > 25:
                assert window
                original_width = window.size.x
                point = (
                    window.pos.x + window.size.x + 2,
                    window.pos.y + window.size.y / 2,
                )
                motion.drag(point, (point[0] + 70, point[1]), evidence.frames)
                stage, entered = 1, evidence.frames
            elif stage == 1 and age > 5:
                assert window
                resized_width = window.size.x
                assert resized_width > original_width + 50, (
                    original_width,
                    resized_width,
                )
                hello_imgui.change_window_size((1280, 800))
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 12:
                assert window and window.size.x > original_width + 50, (
                    window.size.x if window else None
                )
                point = native.find(probe, ("menus", "View", "menu"))
                if point:
                    native.click_point(point, evidence.frames)
                    stage, entered = 3, evidence.frames
            elif stage == 3 and age > 3:
                point = native.find(probe, ("menus", "View", "reset", "run"))
                if point:
                    native.click_point(point, evidence.frames)
                    stage, entered = 4, evidence.frames
            elif stage == 4 and age > 12:
                assert window and 210 < window.size.x < 240
                context = imgui.internal.find_window_by_name("Context")
                assert context and context.dock_id
                assert not editor.current.analysis.jobs.results
                assert editor.playback.snapshot.request is None
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True

        try:
            evidence = run_gui(source, window_size=(1024, 768), on_probe_frame=frame)
        finally:
            motion.close()
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "pointer_splitter_delta": resized_width - original_width,
            "custom_split_survives_window_resize": True,
            "pointer_reset_restores_default_wide_docks": True,
        }
        Path("/tmp/datelier-rebuild-splitter.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
