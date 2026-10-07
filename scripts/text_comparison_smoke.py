"""Native shared tokenizer, source-linked text selection and fresh restore."""

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
from datelier.inspection.text.comparisons.settings import (
    TextComparisonSettings,
    TextComparisonSource,
)
from datelier.inspection.text.types import (
    CorpusMode,
    Normalization,
    TextScope,
    TextSource,
    TokenMode,
    TokenSettings,
)


def run(root: Path, output: Path, restore: bool, view: str) -> dict[str, object]:
    stage = entered = click_stage = 0
    target: tuple[float, float] | None = None
    after_click = 0
    pixels: dict[str, tuple[float, float]] = {}
    workspace = root / "session.datelier"
    tokens = TokenSettings(TokenMode.WHITESPACE, Normalization.NFC, lowercase=True)
    snapshots: list[str] = []
    original_button, original_header, original_tab = (
        imgui.button,
        imgui.collapsing_header,
        imgui.begin_tab_item,
    )

    def capture(label: str) -> None:
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        pixels[label] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)

    def button(label: str, size: imgui.ImVec2 | None = None) -> bool:
        result = original_button(label, size)
        capture(label)
        return result

    def header(label: str, flags: int = 0) -> bool:
        result = original_header(label, flags)
        capture(label)
        return result

    def tab(
        label: str, p_open: bool | None = None, flags: int = 0
    ) -> tuple[bool, bool | None]:
        result = original_tab(label, p_open, flags)
        capture(label)
        return result

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered, click_stage, target, after_click
        io = imgui.get_io()
        params = hello_imgui.get_runner_params()
        if target is not None:
            io.mouse_pos = imgui.ImVec2(*target)
            io.want_set_mouse_pos = True
            age = evidence.frames - entered
            if click_stage == 0 and age > 3:
                io.add_mouse_button_event(0, True)
                click_stage, entered = 1, evidence.frames
            elif click_stage == 1 and age > 3:
                io.add_mouse_button_event(0, False)
                click_stage, entered = 2, evidence.frames
            elif click_stage == 2 and age > 6:
                stage, entered, target = after_click, evidence.frames, None
            return

        def click(label: str, next_stage: int) -> None:
            nonlocal target, after_click, click_stage, entered
            if label not in pixels:
                return
            target = pixels[label]
            assert 0 < target[0] < 1280 and 0 < target[1] < 800, (label, target)
            after_click, click_stage, entered = next_stage, 0, evidence.frames

        if stage == 0:
            if not restore:
                editor.opening.request(
                    (root / "a.csv", root / "b.csv"), editor.active_id
                )
            stage = 1
        elif stage == 1:
            if (
                len(editor.files) != 2
                or any(not f.loader.active for f in editor.files)
                or editor.workspace_jobs.busy
            ):
                return
            first, second = editor.files
            if restore:
                assert editor.text_comparisons[0].tokens == tokens
                assert (
                    editor.text_comparison_jobs.started == 0
                    and not editor.text_comparison_jobs.busy
                )
                assert first.selection.row_ids == second.selection.row_ids == {2}
            else:
                editor.text_comparisons = (
                    TextComparisonSettings(
                        tuple(
                            TextComparisonSource(
                                f.identity,
                                "text",
                                TextSource.INLINE,
                                scope=TextScope(CorpusMode.COLLECTION),
                            )
                            for f in editor.files
                        ),
                        bins=4,
                    ),
                )
                second.text.jobs.settings = replace(
                    second.text.jobs.settings, tokens=tokens
                )
                assert second.loader.revision
                second.selection.choose(second.loader.revision, (2,))
            window = imgui.internal.find_window_by_name("Compare files")
            imgui.internal.set_window_dock(window, 0, imgui.Cond_.always)
            imgui.set_window_pos("Compare files", (20, 65), imgui.Cond_.always)
            imgui.set_window_size("Compare files", (1120, 725), imgui.Cond_.always)
            params.docking_params.focus_dockable_window("Compare files")
            stage, entered = 2, evidence.frames
        elif stage == 2 and evidence.frames - entered > 10:
            click("Text corpora", 3)
        elif stage == 3:
            if restore:
                click("Prepare text comparison", 6)
            else:
                click("Text mappings and shared tokenizer", 4)
        elif stage == 4:
            click("Use active view tokenizer", 5)
        elif stage == 5:
            assert editor.text_comparisons[0].tokens == tokens
            click("Prepare text comparison", 6)
        elif stage == 6:
            if not editor.text_comparison_jobs.active:
                return
            assert [p.tokens for p in editor.text_comparison_jobs.active.profiles] == [
                3,
                8,
            ]
            if restore:
                stage, entered = 7, evidence.frames
            else:
                click("Text mappings and shared tokenizer", 7)
        elif stage == 7 and evidence.frames - entered > 10:
            click("Select matching text rows", 8)
        elif stage == 8:
            if editor.files[0].selection.row_ids != {2}:
                return
            assert editor.files[1].selection.row_ids == {2}
            assert editor.active is editor.files[0]
            click("Statistics", 9)
        elif stage == 9 and evidence.frames - entered > 8:
            click("Token frequencies", 10)
        elif stage == 10 and evidence.frames - entered > 8:
            if view != "frequencies":
                click("Lengths" if view == "lengths" else "Statistics", 15)
            else:
                stage, entered = 15, evidence.frames
        elif stage == 15 and evidence.frames - entered > 8:
            if restore:
                stage = 12
                params.app_shall_exit = True
            else:
                editor.save_workspace(workspace)
                stage = 11
        elif stage == 11 and editor.workspace_jobs.saved:
            stage = 12
            params.app_shall_exit = True

    output.mkdir(parents=True, exist_ok=True)
    with (
        patch.object(imgui, "button", side_effect=button),
        patch.object(imgui, "collapsing_header", side_effect=header),
        patch.object(imgui, "begin_tab_item", side_effect=tab),
    ):
        evidence = run_gui(
            initial_workspace=workspace if restore else None,
            smoke_frames=800,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    assert stage == 12, (stage, pixels)
    path = output / f"text-comparison-{'restored-' if restore else ''}{view}.png"
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(path)
    snapshots.append(str(path))
    return {
        "restore": restore,
        "frames": evidence.frames,
        "shared_tokens": [3, 8],
        "native_selection": True,
        "sources_separate": True,
        "screenshots": snapshots,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-text-comparison")
    )
    parser.add_argument(
        "--view",
        choices=("lengths", "statistics", "frequencies"),
        default="frequencies",
    )
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, args.output, True, args.view)))
        return
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for name, texts in (
            ("a", ["A a", "b", "", None]),
            ("b", ["a b b", "c c c c", "b"]),
        ):
            pl.DataFrame({"id": range(len(texts)), "text": texts}).write_csv(
                root / f"{name}.csv"
            )
        original = [(root / f"{name}.csv").read_bytes() for name in ("a", "b")]
        saved = run(root, args.output, False, args.view)
        child = subprocess.run(
            [
                sys.executable,
                __file__,
                "--restore",
                str(root),
                "--output",
                str(args.output),
                "--view",
                args.view,
            ],
            capture_output=True,
            text=True,
        )
        if child.returncode:
            raise RuntimeError(child.stderr)
        restored = json.loads(child.stdout.strip().splitlines()[-1])
        assert original == [(root / f"{name}.csv").read_bytes() for name in ("a", "b")]
        report = {"save": saved, "reopen": restored, "unchanged_sources": True}
        (args.output / f"text-comparison-{args.view}-native.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
