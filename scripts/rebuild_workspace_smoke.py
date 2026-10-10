"""Separate-process native session/navigation/docking restoration for the rebuild."""

import argparse
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui

from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.pipeline.operations import Sort


def run(root: Path, restore: bool) -> dict[str, object]:
    stage = 0
    completed = False
    original = (root / "data.csv").read_bytes()

    def frame(
        editor: EditorController, _probe: GuiProbe, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, completed
        file = editor.active
        if evidence.frames > 400:
            raise AssertionError((stage, editor.workspace.message))
        if restore:
            if file.inspection is None or editor.workspace.busy:
                return
            assert file.title == "data.csv"
            assert file.profiles.height == 315
            assert file.views.image_height == 345
            assert file.views.text_height == 220
            assert file.selection.row_ids == {1}
            assert file.inspection.dataset.row_ids[0] != 0
            assert editor.navigation.comparing
            assert editor.navigation.context_tab == "History"
            assert not file.analysis.jobs.busy and file.analysis.jobs.latest is None
            assert file.audio.player.snapshot.request is None
            if evidence.frames > 30:
                window = imgui.internal.find_window_by_name("Source browser")
                assert window and window.dock_id != 0
                completed = True
                hello_imgui.get_runner_params().app_shall_exit = True
        elif stage == 0 and file.explorer.active and evidence.frames > 20:
            file.editor.request(Sort(("x",)))
            stage = 1
        elif stage == 1 and not file.editor.busy:
            assert file.inspection is not None
            file.selection.choose(file.inspection.dataset.revision, (1,))
            file.profiles.height = 315
            file.text.original_height = 220
            file.views = replace(file.views, image_height=345, text_height=220)
            editor.choose_route("Compare files")
            editor.navigation.context_tab = "History"
            layout = (
                imgui.save_ini_settings_to_memory()
                + "\n[Datelier][Workbench]\nNativeTree=1\n"
            )
            editor.save_workspace(root / "session.json", layout, (), True, False)
            stage = 2
        elif stage == 2 and not editor.workspace.busy:
            assert editor.workspace.saved is not None, editor.workspace.message
            completed = True
            hello_imgui.get_runner_params().app_shall_exit = True

    evidence = run_gui(
        None if restore else root / "data.csv",
        initial_workspace=root / "session.json" if restore else None,
        preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        on_probe_frame=frame,
    )
    assert completed
    assert (root / "data.csv").read_bytes() == original
    report: dict[str, object] = {
        "mode": "restore" if restore else "save",
        "frames": evidence.frames,
        "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
        "source_preserved": True,
        "implicit_operations": 0,
    }
    print(json.dumps(report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    args = parser.parse_args()
    if args.restore:
        run(args.restore, True)
        return
    with TemporaryDirectory(prefix="datelier-rebuild-workspace-") as directory:
        root = Path(directory)
        rng = np.random.default_rng(17)
        pl.DataFrame({"x": rng.normal(size=100), "y": rng.normal(size=100)}).write_csv(
            root / "data.csv"
        )
        saved = run(root, False)
        result = subprocess.run(
            [sys.executable, __file__, "--restore", str(root)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        restored = json.loads(result.stdout.strip().splitlines()[-1])
        Path("/tmp/datelier-rebuild-workspace.json").write_text(
            json.dumps({"save": saved, "restore": restored}, indent=2) + "\n"
        )
        print(result.stdout.strip())


if __name__ == "__main__":
    main()
