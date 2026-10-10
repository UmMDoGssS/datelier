"""Render Schema list choices, inject a combo change, and restore its recipe."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.core.column_roles import ColumnRole
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.pipeline.editing import HistoryAction


def run(root: Path, output: Path, *, restore: bool) -> dict[str, object]:
    stage = entered = 0
    change = False
    choices: list[str] = []
    original = imgui.combo
    workspace = root / "session.datelier.json"

    def combo(label: str, index: int, labels: list[str]) -> tuple[bool, int]:
        nonlocal change, choices
        result = original(label, index, labels)
        if label == "##role values":
            choices = labels
            assert "list[numeric]" in labels and "list[category]" in labels
            assert "list[text]" not in labels
            if change:
                change = False
                return True, labels.index("list[category]")
        elif label == "##role text":
            assert "list[text]" in labels and "list[category]" in labels
        return result

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered, change
        file = editor.active
        if file.loader.active is None:
            ready = next((f for f in editor.files if f.loader.active), None)
            if ready and restore:
                editor.activate(ready.identity)
            return
        dataset = file.loader.active.dataset
        age = evidence.frames - entered
        if stage == 0:
            assert dataset.role("text").role == ColumnRole.LIST_TEXT
            assert not file.text.jobs.busy and file.text.jobs.profile is None
            if restore:
                assert dataset.role("values").override == ColumnRole.LIST_CATEGORY
                assert file.exploration.profile.selection.columns == ("values",)
                file.exploration.profile.area.expanded = True
                stage, entered = 4, evidence.frames
            else:
                assert dataset.role("values").role == ColumnRole.LIST_NUMERIC
                hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                    "Schema and nulls"
                )
                stage, entered = 1, evidence.frames
        elif stage == 1 and choices and age > 10:
            change = True
            stage, entered = 2, evidence.frames
        elif stage == 2 and dataset.role("values").override == ColumnRole.LIST_CATEGORY:
            file.editor.request(HistoryAction.UNDO)
            stage, entered = 3, evidence.frames
        elif stage == 3 and not file.editor.busy:
            assert dataset.role("values").role == ColumnRole.LIST_NUMERIC
            file.editor.request(HistoryAction.REDO)
            stage, entered = 4, evidence.frames
        elif stage == 4 and not file.editor.busy:
            assert dataset.role("values").override == ColumnRole.LIST_CATEGORY
            file.exploration.tab = "Profiles"
            file.exploration.profile.selection.columns = ("values",)
            file.exploration.profile.area.expanded = True
            hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                "Explore"
            )
            stage, entered = 5, evidence.frames
        elif stage == 5 and age > 20:
            group = file.explorer.profiles.active
            if group is None:
                return
            profile = group.profiles.columns[0]
            assert profile.name == "values" and profile.statistics is None
            assert profile.distribution.counts == (2, 2)
            assert not file.text.jobs.busy and not file.analysis.jobs.results
            if restore:
                stage = 7
                hello_imgui.get_runner_params().app_shall_exit = True
            else:
                editor.save_workspace(workspace)
                stage, entered = 6, evidence.frames
        elif stage == 6 and editor.workspace_jobs.saved is not None:
            stage = 7
            hello_imgui.get_runner_params().app_shall_exit = True

    with patch.object(imgui, "combo", new=combo):
        evidence = run_gui(
            None if restore else root / "source.json",
            initial_workspace=workspace if restore else None,
            smoke_frames=300,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    assert stage == 7, (stage, choices)
    output.mkdir(parents=True, exist_ok=True)
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / ("roles-restored.png" if restore else "roles.png")
    )
    return {
        "frames": evidence.frames,
        "restore": restore,
        "schema_choices": choices,
        "combo_change_injected": not restore,
        "role": "list[category]",
        "no_implicit_text_or_ml": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    parser.add_argument("--output", type=Path, default=Path("/tmp/datelier-list-roles"))
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, args.output, restore=True)))
        return
    with TemporaryDirectory(prefix="datelier-list-roles-") as directory:
        root = Path(directory)
        source = root / "source.json"
        content = json.dumps(
            [
                {"values": [1, 2, 2], "text": ["one two three"]},
                {"values": [1], "text": ["four five six"]},
            ]
        )
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
        (args.output / "roles.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
