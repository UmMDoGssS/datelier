"""Native source-linked token selection, long text paging and session restore."""

import argparse
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import polars as pl
from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.inspection.records.types import RecordMode
from datelier.inspection.text.types import (
    Normalization,
    TextSource,
    TokenMode,
    TokenSettings,
)
from datelier.pipeline.operations import Sort


def run(root: Path, output: Path, *, restore: bool) -> dict[str, object]:
    stage = entered = 0
    pixels: dict[str, tuple[float, float]] = {}
    original_button, original_small = imgui.button, imgui.small_button
    workspace = root / "session.datelier.json"

    def capture(label: str) -> None:
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        pixels[label] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)

    def button(label: str, size: imgui.ImVec2 | None = None) -> bool:
        result = original_button(label, size)
        if label == "Inspect text tokens":
            capture(label)
        return result

    def small(label: str) -> bool:
        result = original_small(label)
        if label == "End of text":
            capture(label)
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
        jobs = file.text.jobs
        age = evidence.frames - entered
        io = imgui.get_io()

        def click(point: tuple[float, float], next_stage: int) -> None:
            nonlocal stage, entered
            io.mouse_pos = imgui.ImVec2(*point)
            io.want_set_mouse_pos = True
            stage, entered = next_stage, evidence.frames

        if stage == 0:
            hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                "Inspect"
            )
            if restore:
                assert file.inspect.settings.mode == RecordMode.SELECTION
                assert jobs.settings.viewport.selected_token == 2
                assert (
                    not jobs.busy
                    and jobs.active is None
                    and file.text.pages.active is None
                )
                stage, entered = 20, evidence.frames
            else:
                file.inspect.settings = replace(
                    file.inspect.settings,
                    gallery=False,
                    primary="body",
                    supporting=("id", "support"),
                )
                jobs.settings = replace(
                    jobs.settings,
                    source=TextSource.INLINE,
                    tokens=TokenSettings(TokenMode.CHARACTER, Normalization.NFC),
                )
                stage, entered = 1, evidence.frames
        elif stage == 1 and age > 10 and "Inspect text tokens" in pixels:
            click(pixels["Inspect text tokens"], 2)
        elif stage in (2, 5, 9, 21, 25) and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = stage + 1, evidence.frames
        elif stage in (3, 6, 10, 22, 26) and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = stage + 1, evidence.frames
        elif stage == 4 and jobs.active and file.text.pages.active and age > 10:
            assert jobs.active.document.origin.row_id == 0
            # Scroll to the virtual token table without scrolling its source pane.
            io.mouse_pos = imgui.ImVec2(*pixels["Inspect text tokens"])
            io.want_set_mouse_pos = True
            io.add_mouse_wheel_event(0, -5)
            stage, entered = 41, evidence.frames
        elif stage == 41 and 2 in file.text.document.token_pixels and age > 8:
            click(file.text.document.token_pixels[2], 5)
        elif (
            stage == 7
            and jobs.settings.viewport.selected_token == 2
            and file.text.pages.active
            and age > 10
        ):
            assert file.text.pages.active.selected_span == (2, 4)
            assert file.text.pages.active.selected_source == "e\u0301"
            # Bring the page controls back into view.
            io.mouse_pos = imgui.ImVec2(500, 410)
            io.want_set_mouse_pos = True
            io.add_mouse_wheel_event(0, 8)
            stage, entered = 8, evidence.frames
        elif stage == 8 and age > 10:
            click(pixels["End of text"], 9)
        elif stage == 11 and file.text.pages.active and age > 10:
            page = file.text.pages.active
            assert jobs.active and page.end == len(jobs.active.document.text)
            assert "FINAL" in "".join(r.text for line in page.lines for r in line.runs)
            file.selection.choose(file.loader.active.dataset.revision, (0,))
            file.inspect.settings = replace(
                file.inspect.settings, mode=RecordMode.SELECTION
            )
            file.editor.request(Sort(("id",), True))
            stage = 12
        elif stage == 12 and not file.editor.busy and file.inspect.jobs.active:
            if not file.selection.row_ids:
                file.selection.choose(file.loader.active.dataset.revision, (0,))
                return
            if file.inspect.jobs.active.row_ids.to_list() != [0]:
                return
            file.text.request_record(file, "body", 1)
            # Keep a source accent selection for fresh-process verification.
            jobs.settings = replace(
                jobs.settings,
                viewport=replace(jobs.settings.viewport, start=0, selected_token=2),
            )
            stage = 13
        elif stage == 13 and jobs.active and file.text.pages.active:
            assert jobs.active.document.origin.row_id == 0
            assert file.text.pages.active.selected_source == "e\u0301"
            page = file.inspect.jobs.get(0)
            if not page:
                return
            assert (
                page.cards[0].position == 1
                and page.cards[0].fields[1].text == "source-zero"
            )
            editor.save_workspace(workspace)
            stage = 14
        elif stage == 14 and editor.workspace_jobs.saved:
            hello_imgui.get_runner_params().app_shall_exit = True
        elif stage == 20 and age > 10 and "Inspect text tokens" in pixels:
            click(pixels["Inspect text tokens"], 21)
        elif stage == 23 and jobs.active and file.text.pages.active and age > 10:
            assert (
                jobs.active.document.origin.row_id == 0 and jobs.settings.position == 1
            )
            assert file.text.pages.active.selected_span == (2, 4)
            assert file.text.document.rendered_tokens < 30
            stage = 24
            hello_imgui.get_runner_params().app_shall_exit = True

    with (
        patch.object(imgui, "button", side_effect=button),
        patch.object(imgui, "small_button", side_effect=small),
    ):
        evidence = run_gui(
            None if restore else root / "source.csv",
            initial_workspace=workspace if restore else None,
            smoke_frames=600,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    output.mkdir(parents=True, exist_ok=True)
    screenshot = output / (
        "text-inspect-restored.png" if restore else "text-inspect.png"
    )
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        screenshot
    )
    assert stage == (24 if restore else 14), (stage, pixels)
    return {
        "frames": evidence.frames,
        "restore": restore,
        "screenshot": str(screenshot),
        "native_span": [2, 4],
        "source_row": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-text-inspect")
    )
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, args.output, restore=True)))
        return
    with TemporaryDirectory() as directory:
        root = Path(directory)
        text = "A e\u0301 中🙂\n" + ("long original text 中🙂\n" * 500) + "FINAL"
        pl.DataFrame(
            {
                "id": [1, 2],
                "body": [text, "another document"],
                "support": ["source-zero", "source-one"],
            }
        ).write_csv(root / "source.csv")
        saved = run(root, args.output, restore=False)
        completed = subprocess.run(
            [
                sys.executable,
                __file__,
                "--restore",
                str(root),
                "--output",
                str(args.output),
            ],
            capture_output=True,
            text=True,
        )
        if completed.returncode:
            raise RuntimeError(completed.stderr)
        restored = json.loads(completed.stdout.strip().splitlines()[-1])
        report = {
            "save": saved,
            "reopen": restored,
            "original_code_points": len(text),
            "full_eof": True,
            "sort_support_alignment": True,
        }
        (args.output / "text-inspect-native.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
