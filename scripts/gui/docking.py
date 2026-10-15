"""Native dock reassignment survives compact mode; pointer Reset restores defaults."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui, imgui

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from scripts.support.input import NativeInput


def main() -> None:
    with TemporaryDirectory(prefix="datelier-custom-docks-") as directory:
        source = Path(directory) / "data.csv"
        source.write_text("x,y\n1.0,2.0\n3.0,4.0\n")
        original = source.read_bytes()
        native = NativeInput()
        stage = entered = destination = 0
        done = False

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, destination, done
            age = evidence.frames - entered
            source_window = imgui.internal.find_window_by_name("Source browser")
            canvas = imgui.internal.find_window_by_name("Explore")
            if evidence.frames > 250:
                raise AssertionError(
                    (stage, source_window.dock_id if source_window else None)
                )
            if native.advance(evidence.frames):
                return
            suffix: tuple[str, ...] | None = None
            if stage == 0 and editor.current.inspection and evidence.frames > 20:
                assert source_window and canvas
                assert source_window.dock_id != canvas.dock_id
                destination = canvas.dock_id
                imgui.internal.dock_builder_dock_window("Source browser", destination)
                stage, entered = 1, evidence.frames
            elif stage == 1 and age > 8:
                assert source_window and canvas
                assert source_window.dock_id == canvas.dock_id == destination
                suffix = ("menus", "View", "menu")
            elif stage == 2 and age > 3:
                suffix = ("menus", "View", "reset", "run")
            elif stage == 3 and age > 8:
                assert source_window and canvas
                assert source_window.dock_id != canvas.dock_id
                assert 210 < source_window.size.x < 240
                suffix = ("menus", "View", "menu")
            elif stage == 4 and age > 3:
                suffix = ("menus", "View", "context", "run")
            elif stage == 5 and age > 5:
                context = imgui.internal.find_window_by_name("Context")
                assert context and context.dock_id == 0
                assert source_window and source_window.dock_id != canvas.dock_id
                assert source.read_bytes() == original
                assert not editor.current.analysis.jobs.results
                assert editor.playback.snapshot.request is None
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix:
                point = native.find(probe, suffix)
                if point:
                    native.click_point(point, evidence.frames)
                    stage, entered = stage + 1, evidence.frames

        evidence = run_gui(source, window_size=(1024, 768), on_probe_frame=frame)
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "programmatic_native_dock_assignment_preserved": True,
            "pointer_reset_restores_default_compact_layout": True,
            "pointer_drawer_after_reset_remains_undocked": True,
            "source_preserved": True,
            "implicit_operations": 0,
        }
        Path("/tmp/datelier-rebuild-docking.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
