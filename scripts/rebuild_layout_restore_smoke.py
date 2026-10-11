"""Saved default docks adapt across sizes in a fresh native process."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui, imgui

from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.workspace.preferences import Preferences, save_preferences


def run(root: Path, restore: bool) -> dict[str, object]:
    done = False
    source = root / "data.csv"
    original = source.read_bytes()

    def frame(
        editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
    ) -> None:
        nonlocal done
        if evidence.frames < 25 or editor.current.inspection is None:
            return
        context = imgui.internal.find_window_by_name("Context")
        if restore:
            # The saved tree came from a wide window with a docked Context.
            assert context is None or context.hidden
            source_window = imgui.internal.find_window_by_name("Source browser")
            assert source_window and 210 < source_window.size.x < 240
        else:
            assert context and context.dock_id
            layout = (
                imgui.save_ini_settings_to_memory()
                + "\n[Datelier][Workbench]\nNativeTree=1\n"
            )
            save_preferences(root / "restored.json", Preferences(layout=layout))
        assert source.read_bytes() == original
        assert not editor.current.analysis.jobs.results
        assert editor.playback.snapshot.request is None
        done = True
        hello_imgui.get_runner_params().app_shall_exit = True

    evidence = run_gui(
        source,
        window_size=(1024, 768) if restore else (1280, 800),
        preferences_path=root / ("restored.json" if restore else "initial.json"),
        on_probe_frame=frame,
        smoke_frames=150,
    )
    assert done
    return {
        "mode": "compact-restore" if restore else "wide-save",
        "frames": evidence.frames,
        "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
        "source_preserved": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, True)))
        return
    with TemporaryDirectory(prefix="datelier-adaptive-layout-") as directory:
        root = Path(directory)
        (root / "data.csv").write_text("x###,y\n1.0,2.0\n3.0,4.0\n")
        saved = run(root, False)
        completed = subprocess.run(
            [sys.executable, __file__, "--restore", str(root)],
            check=True,
            capture_output=True,
            text=True,
        )
        report = {
            "saved": saved,
            "restored": json.loads(completed.stdout.strip().splitlines()[-1]),
        }
        Path("/tmp/datelier-rebuild-layout-restore.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
