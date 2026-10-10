"""Render full object/list cells and restore their sorted Inspect session."""

import argparse
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from imgui_bundle import hello_imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.inspect import view
from datelier.gui.tabs import EditorTabs
from datelier.inspection.records.types import RecordField
from datelier.pipeline.operations import Sort


def run(root: Path, output: Path, *, restore: bool) -> dict[str, object]:
    stage = entered = rendered = 0
    names: set[str] = set()
    original = view.show_nested
    workspace = root / "session.datelier.json"

    def nested(field: RecordField, *, gallery: bool) -> None:
        nonlocal rendered
        original(field, gallery=gallery)
        names.add(field.name)
        rendered += 1

    def screenshot(label: str) -> None:
        output.mkdir(parents=True, exist_ok=True)
        Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
            output / f"{label}.png"
        )

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered
        file = editor.active
        if file.loader.active is None:
            ready = next((f for f in editor.files if f.loader.active), None)
            if ready and restore:
                editor.activate(ready.identity)
            return
        age = evidence.frames - entered
        if stage == 0:
            page = file.loader.active.first_page
            assert "{ ... }" in page.rows[0]
            assert any("[ ... ] (2 items)" in row for row in page.rows)
            if restore:
                assert file.loader.active.dataset.row_ids.to_list() == [1, 0]
                assert file.inspect.settings.primary == "xs"
                assert not file.inspect.settings.gallery
                assert not file.analysis.jobs.results and not file.text.jobs.busy
                stage, entered = 3, evidence.frames
            else:
                file.editor.request(Sort(("id",)))
                stage, entered = 1, evidence.frames
        elif stage == 1 and not file.editor.busy:
            assert file.loader.active.dataset.row_ids.to_list() == [1, 0]
            file.exploration.tab = "Inspect"
            file.inspect.settings = replace(
                file.inspect.settings,
                primary="obj",
                supporting=("id", "xs"),
                gallery=False,
                focus=1,
            )
            hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                "Explore"
            )
            stage, entered = 2, evidence.frames
        elif stage in (2, 3) and rendered > 5 and age > 15:
            page = file.inspect.jobs.get(0)
            if page is None:
                return
            primary = page.cards[1].primary
            assert primary is not None and not primary.truncated
            assert primary.lines is not None
            assert page.cards[1].row_id == 0
            if stage == 2:
                assert primary.name == "obj" and "last entry" in primary.text
                assert len(primary.text) > 4096
                file.inspect.settings = replace(file.inspect.settings, primary="xs")
                stage, entered = 3, evidence.frames
            elif primary.name == "xs" and "xs" in names:
                assert json.loads(primary.text) == [[1, 2], [3, None]]
                if restore:
                    stage = 5
                    hello_imgui.get_runner_params().app_shall_exit = True
                else:
                    editor.save_workspace(workspace)
                    stage, entered = 4, evidence.frames
        elif stage == 4 and editor.workspace_jobs.saved is not None:
            stage = 5
            hello_imgui.get_runner_params().app_shall_exit = True

    with patch.object(view, "show_nested", new=nested):
        evidence = run_gui(
            None if restore else root / "source.json",
            initial_workspace=workspace if restore else None,
            smoke_frames=300,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    assert stage == 5, (stage, names)
    screenshot("restored" if restore else "list")
    return {
        "frames": evidence.frames,
        "rendered_fields": sorted(names),
        "restore": restore,
        "sorted_source_ids": [1, 0],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-nested-inspect")
    )
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, args.output, restore=True)))
        return
    with TemporaryDirectory(prefix="datelier-nested-inspect-") as directory:
        root = Path(directory)
        source = root / "source.json"
        content = json.dumps(
            [
                {
                    "id": 2,
                    "obj": {"text": "café 中 " * 1000, "tail": "last entry"},
                    "xs": [[1, 2], [3, None]],
                },
                {"id": 1, "obj": {"text": "short", "tail": "second"}, "xs": []},
            ],
            ensure_ascii=False,
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
        (args.output / "inspect.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
