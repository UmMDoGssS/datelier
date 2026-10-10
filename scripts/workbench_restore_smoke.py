"""Fresh-process canvas/context and viewport restoration without implicit commands."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.inspection.audio.playback.controller import PlaybackPhase
from datelier.inspection.comparison_settings import ComparisonSettings
from datelier.workspace.preferences import read_preferences
from datelier.workspace.session_storage import read_session_workspace


def stage(root: Path, restore: bool) -> None:
    observed = False
    saved = False

    def frame(
        editor: EditorSession, _tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal observed, saved
        file = editor.active
        if (
            file.loader.active is None
            or file.explorer.active is None
            or evidence.frames < 25
        ):
            return
        if not restore and not saved:
            file.images.area.height = 340
            file.text.document.area.height = 210
            file.text.document.token_area.height = 290
            editor.comparisons = (ComparisonSettings(),)
            editor.navigation.choose_canvas(True)
            editor.navigation.context_tab = "History"
            editor.save_workspace(root / "session.datelier")
            saved = True
        elif restore:
            assert editor.navigation.comparing
            assert editor.navigation.context_tab == "History"
            assert (
                file.images.area.height,
                file.text.document.area.height,
                file.text.document.token_area.height,
            ) == (340, 210, 290)
            assert editor.comparisons == (ComparisonSettings(),)
            assert not file.analysis.jobs.results and not file.analysis.jobs.busy
            assert file.audio.player.snapshot.phase == PlaybackPhase.IDLE
            assert not file.text.jobs.busy
            observed = True
            hello_imgui.get_runner_params().app_shall_exit = True
        elif editor.workspace_jobs.saved:
            observed = True
            hello_imgui.get_runner_params().app_shall_exit = True

    run_gui(
        None if restore else root / "source.parquet",
        initial_workspace=root / "session.datelier" if restore else None,
        preferences_path=root / "prefs.json",
        smoke_frames=400,
        on_editor_frame=frame,
    )
    assert observed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    if args.root:
        stage(args.root, args.restore)
        return
    with TemporaryDirectory(prefix="datelier-workbench-restore-") as directory:
        root = Path(directory)
        pl.DataFrame(
            np.random.default_rng(5).normal(size=(64, 3)), schema=["x", "y", "z"]
        ).write_parquet(root / "source.parquet")
        original = (root / "source.parquet").read_bytes()
        for restore in (False, True):
            command = [sys.executable, __file__, "--root", str(root)]
            if restore:
                command.append("--restore")
            subprocess.run(command, check=True)
        assert (root / "source.parquet").read_bytes() == original
        workspace = read_session_workspace(root / "session.datelier")
        assert workspace.version == 3 and workspace.layout_version == 2
        assert read_preferences(root / "prefs.json")[1] == "Preferences restored."
        print(
            json.dumps(
                dict(
                    fresh_process=True,
                    canvas_context=True,
                    media_sizes=True,
                    no_implicit_commands=True,
                    source_preserved=True,
                    session_version=3,
                    preferences_version=2,
                )
            )
        )


if __name__ == "__main__":
    main()
