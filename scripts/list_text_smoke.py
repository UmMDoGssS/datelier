"""Render List[Text] controls/statistics and restore its selected nested element."""

import argparse
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.core.column_roles import ColumnRole
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.gui.text import profiles
from datelier.inspection.text.statistics import TextProfile
from datelier.inspection.text.types import CorpusMode, TextScope
from datelier.pipeline.operations import SetColumnRole


def run(root: Path, output: Path, *, restore: bool) -> dict[str, object]:
    stage = entered = 0
    tables: set[str] = set()
    controls: set[str] = set()
    original_table, original_input = imgui.begin_table, imgui.input_int
    original_stats, original_header = profiles.statistics, imgui.collapsing_header
    workspace = root / "session.datelier.json"

    def statistics(profile: TextProfile) -> None:
        position = imgui.get_cursor_pos_y()
        original_stats(profile)
        imgui.set_scroll_y(imgui.get_scroll_max_y() if restore else position - 60)

    def header(label: str, flags: int = 0) -> bool:
        result = original_header(label, flags)
        return True if label == "Text settings" else result

    def integer(
        label: str, value: int, step: int = 1, step_fast: int = 100, flags: int = 0
    ) -> tuple[bool, int]:
        result = original_input(label, value, step, step_fast, flags)
        if label == "Text list element (1-based)":
            controls.add(label)
        return result

    def table(
        label: str,
        count: int,
        flags: int = 0,
        size: imgui.ImVec2 | None = None,
        inner_width: float = 0,
    ) -> bool:
        result = original_table(
            label, count, flags, size or imgui.ImVec2(), inner_width
        )
        if result and label in (
            "List statistics",
            "List shapes",
            "Corpus statistics",
            "Element length statistics",
        ):
            tables.add(label)
        return result

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
        dataset, jobs = file.loader.active.dataset, file.text.jobs
        age = evidence.frames - entered
        if stage == 0:
            assert not jobs.busy and jobs.profile is None and jobs.active is None
            if restore:
                assert dataset.role("text").override == ColumnRole.LIST_TEXT
                assert jobs.settings.element_index == 1
                assert jobs.settings.scope.mode == CorpusMode.COLLECTION
                assert file.exploration.profile.selection.columns == ("text",)
                stage = 2
            else:
                assert dataset.role("text").role == ColumnRole.LIST_CATEGORY
                file.editor.request(SetColumnRole("text", ColumnRole.LIST_TEXT))
                stage = 1
            entered = evidence.frames
        elif stage == 1 and not file.editor.busy:
            assert dataset.role("text").override == ColumnRole.LIST_TEXT
            stage, entered = 2, evidence.frames
        elif stage == 2:
            file.exploration.tab = "Profiles"
            file.exploration.profile.selection.columns = ("text",)
            jobs.settings = replace(
                jobs.settings,
                column="text",
                element_index=1,
                scope=TextScope(CorpusMode.COLLECTION),
            )
            file.text.sync(file)
            hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                "Explore"
            )
            stage, entered = 3, evidence.frames
        elif (
            stage == 3
            and age > 15
            and not jobs.busy
            and jobs.profile is None
            and {"List statistics", "List shapes"} <= tables
        ):
            jobs.request_profile()
        elif stage == 3 and jobs.profile and jobs.active is None and not jobs.busy:
            jobs.request_document()
        elif (
            stage == 3
            and age > 25
            and len(tables) == 4
            and jobs.profile
            and jobs.active
        ):
            result = jobs.profile.profile
            assert result.is_list and (
                result.requested_records,
                result.documents,
                result.tokens,
            ) == (4, 4, 4)
            assert result.records["element_path"].to_list() == [
                [0, 0],
                [0, 1],
                [0, 0],
                [0, 1],
            ]
            assert jobs.active.document.origin.element_path == (0, 1)
            assert jobs.active.document.text == "b"
            assert file.text.pages.active is not None
            assert controls
            assert not file.analysis.jobs.results
            if restore:
                stage = 5
                hello_imgui.get_runner_params().app_shall_exit = True
            else:
                editor.save_workspace(workspace)
                stage, entered = 4, evidence.frames
        elif stage == 4 and editor.workspace_jobs.saved is not None:
            stage = 5
            hello_imgui.get_runner_params().app_shall_exit = True

    with (
        patch.object(imgui, "begin_table", new=table),
        patch.object(imgui, "input_int", new=integer),
        patch.object(imgui, "collapsing_header", new=header),
        patch.object(profiles, "statistics", new=statistics),
    ):
        evidence = run_gui(
            None if restore else root / "source.json",
            initial_workspace=workspace if restore else None,
            smoke_frames=350,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    assert stage == 5, (stage, tables, controls)
    output.mkdir(parents=True, exist_ok=True)
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / ("list-text-restored.png" if restore else "list-text.png")
    )
    return {
        "frames": evidence.frames,
        "restore": restore,
        "tables": sorted(tables),
        "element_controls": sorted(controls),
        "role": "List[Text]",
        "element_path": [0, 1],
        "no_implicit_text_or_ml": True,
        "commands_dispatched_explicitly": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    parser.add_argument("--output", type=Path, default=Path("/tmp/datelier-list-text"))
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, args.output, restore=True)))
        return
    with TemporaryDirectory(prefix="datelier-list-text-") as directory:
        root = Path(directory)
        source = root / "source.json"
        content = json.dumps(
            [
                {"id": 0, "text": [["a a", "b"]]},
                {"id": 1, "text": [["c", ""]]},
                {"id": 2, "text": []},
                {"id": 3, "text": None},
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
        (args.output / "list-text.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
