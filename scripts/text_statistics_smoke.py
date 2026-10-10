"""Render text statistics tables and restore their selection in a fresh process."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.gui.text import profiles
from datelier.inspection.text.statistics import TextProfile


def run(root: Path, output: Path, *, restore: bool) -> dict[str, object]:
    tables: set[str] = set()
    original = imgui.begin_table
    started = saved = False
    workspace = root / "session.datelier.json"

    def statistics(profile: TextProfile) -> None:
        profiles_statistics(profile)
        if len(tables) == 1:
            imgui.set_scroll_y(imgui.get_scroll_max_y())

    profiles_statistics = profiles.statistics

    def table(
        label: str,
        count: int,
        flags: int = 0,
        size: imgui.ImVec2 | None = None,
        inner_width: float = 0,
    ) -> bool:
        result = original(label, count, flags, size or imgui.ImVec2(), inner_width)
        if result and label in ("Corpus statistics", "Document length statistics"):
            tables.add(label)
        return result

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal started, saved
        file = editor.active
        if file.loader.active is None:
            ready = next((f for f in editor.files if f.loader.active), None)
            if ready and restore:
                editor.activate(ready.identity)
            return
        if not started:
            started = True
            if restore:
                assert file.exploration.profile.selection.columns == ("body",)
                assert file.text.jobs.profile is None and not file.text.jobs.busy
            file.exploration.profile.selection.columns = ("body",)
            file.exploration.tab = "Profiles"
            file.text.jobs.settings = file.text.jobs.settings.__replace__(column="body")
            file.text.sync(file)
            file.text.jobs.request_profile()
            hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                "Explore"
            )
        if len(tables) == 2 and file.text.profiles.shown > 10:
            profile = file.text.jobs.profile
            assert profile is not None
            assert profile.profile.documents == 3 and profile.profile.tokens == 5
            if not saved:
                editor.save_workspace(
                    workspace, layout=imgui.save_ini_settings_to_memory()
                )
                saved = True
            elif editor.workspace_jobs.saved is not None:
                hello_imgui.get_runner_params().app_shall_exit = True

    with (
        patch.object(imgui, "begin_table", new=table),
        patch.object(profiles, "statistics", new=statistics),
    ):
        evidence = run_gui(
            None if restore else root / "source.csv",
            initial_workspace=workspace if restore else None,
            smoke_frames=300,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    assert len(tables) == 2 and saved, (tables, started, saved)
    output.mkdir(parents=True, exist_ok=True)
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / ("restored.png" if restore else "tables.png")
    )
    return {"frames": evidence.frames, "tables": sorted(tables), "restore": restore}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-text-tables")
    )
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, args.output, restore=True)))
        return
    with TemporaryDirectory(prefix="datelier-text-tables-") as directory:
        root = Path(directory)
        source = root / "source.csv"
        content = 'id,body\n1,alpha beta beta\n2,café 中\n3,""\n'
        source.write_text(content)
        report: dict[str, object] = {"open": run(root, args.output, restore=False)}
        child = subprocess.run(
            [
                sys.executable,
                __file__,
                "--restore",
                str(root),
                "--output",
                str(args.output),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        report["restore"] = json.loads(child.stdout.strip().splitlines()[-1])
        assert source.read_text() == content
        report["source_preserved"] = True
        (args.output / "tables.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
