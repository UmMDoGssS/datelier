"""Native explicit BPE/Unigram commands and separate-process artifact recovery."""

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
from datelier.inspection.text.types import (
    CorpusMode,
    Normalization,
    TextScope,
    TextSettings,
    TextSource,
    TokenMode,
    TokenSettings,
    TrainingSettings,
)


def run(root: Path, output: Path, *, restore: bool) -> dict[str, object]:
    stage = entered = 0
    pixels: dict[str, tuple[float, float]] = {}
    original_button, original_header = imgui.button, imgui.collapsing_header
    workspace = root / "session.datelier.json"

    def capture(label: str) -> None:
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        pixels[label] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)

    def button(label: str, size: imgui.ImVec2 | None = None) -> bool:
        result = original_button(label, size)
        if label in ("Train local tokenizer", "Prepare text record"):
            capture(label)
            if label == "Train local tokenizer" and stage in (4, 8):
                imgui.set_scroll_here_y(0.7)
        return result

    def header(label: str, flags: int = 0) -> bool:
        result = original_header(label, flags)
        if label == "Local tokenizer training":
            capture(label)
        return result

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered
        file = editor.active
        if file.loader.active is None:
            ready = next((f for f in editor.files if f.loader.active), None)
            if restore and ready:
                editor.activate(ready.identity)
            return
        jobs = file.text.jobs
        age = evidence.frames - entered
        io = imgui.get_io()

        def click(label: str, next_stage: int) -> None:
            nonlocal stage, entered
            io.mouse_pos = imgui.ImVec2(*pixels[label])
            io.want_set_mouse_pos = True
            stage, entered = next_stage, evidence.frames

        if stage == 0:
            hello_imgui.get_runner_params().docking_params.focus_dockable_window("Text")
            if restore:
                assert jobs.settings.tokens.mode == TokenMode.UNIGRAM
                assert jobs.settings.scope.mode == CorpusMode.SELECTION
                assert (
                    jobs.settings.tokens.artifact
                    and jobs.settings.tokens.artifact.provenance_path
                )
                assert not jobs.busy and jobs.active is None
                stage, entered = 20, evidence.frames
            else:
                file.selection.choose(file.loader.active.dataset.revision, (0, 2, 3))
                jobs.settings = TextSettings(
                    "text",
                    TextSource.INLINE,
                    tokens=TokenSettings(
                        normalization=Normalization.NFC, lowercase=True
                    ),
                    scope=TextScope(CorpusMode.SELECTION),
                    training=TrainingSettings(
                        vocabulary_size=25,
                        min_frequency=1,
                        output_path=str(root / "bpe.json"),
                    ),
                )
                assert not jobs.busy
                stage, entered = 1, evidence.frames
        elif stage == 1 and age > 10 and "Local tokenizer training" in pixels:
            assert not (root / "bpe.json").exists()
            click("Local tokenizer training", 2)
        elif stage in (2, 5, 9, 13, 21) and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = stage + 1, evidence.frames
        elif stage in (3, 6, 10, 14, 22) and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = stage + 1, evidence.frames
        elif stage == 4 and age > 12 and "Train local tokenizer" in pixels:
            assert not (root / "bpe.json").exists()
            click("Train local tokenizer", 5)
        elif stage == 7 and jobs.message.startswith("Trained BPE"):
            assert (root / "bpe.json").is_file()
            saved = json.loads((root / "bpe.json.provenance.json").read_text())
            assert saved["source_row_ids"] == [0, 2, 3] and saved["documents"] == 1
            jobs.settings = replace(
                jobs.settings,
                training=replace(
                    jobs.settings.training,
                    mode=TokenMode.UNIGRAM,
                    output_path=str(root / "unigram.json"),
                ),
            )
            stage, entered = 8, evidence.frames
        elif stage == 8 and age > 12:
            assert not (root / "unigram.json").exists()
            click("Train local tokenizer", 9)
        elif stage == 11 and jobs.message.startswith("Trained Unigram"):
            assert (root / "unigram.json").is_file()
            # Close the form so artifact/result controls are immediately visible.
            hello_imgui.get_runner_params().docking_params.focus_dockable_window("Text")
            stage, entered = 12, evidence.frames
        elif stage == 12 and age > 8:
            # The header is at the top of a scrollable panel after form input.
            file.panel_scroll["Text"] = (0, 0)
            editor.save_workspace(workspace)
            stage = 16
        elif stage == 16 and editor.workspace_jobs.saved:
            hello_imgui.get_runner_params().app_shall_exit = True
        elif stage == 20 and age > 10:
            jobs.request_document()
            stage = 23
        elif stage == 23 and jobs.active:
            assert jobs.active.normalized == "hello hello 中 é"
            assert jobs.active.document.origin.row_id == 0
            assert jobs.active.document.origin.file_id == file.identity
            hello_imgui.get_runner_params().app_shall_exit = True

    with (
        patch.object(imgui, "button", side_effect=button),
        patch.object(imgui, "collapsing_header", side_effect=header),
    ):
        evidence = run_gui(
            None if restore else root / "source.csv",
            initial_workspace=workspace if restore else None,
            smoke_frames=300,
            on_editor_frame=frame,
            preferences_path=root
            / ("restored-prefs.json" if restore else "prefs.json"),
        )
    output.mkdir(parents=True, exist_ok=True)
    screenshot = output / (
        "training-restored.png" if restore else "training-controls.png"
    )
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        screenshot
    )
    assert stage == (23 if restore else 16), (stage, pixels)
    return {
        "frames": evidence.frames,
        "stage": stage,
        "restore": restore,
        "screenshot": str(screenshot),
        "implicit_training": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-text-training")
    )
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, args.output, restore=True)))
        return
    with TemporaryDirectory() as directory:
        root = Path(directory)
        pl.DataFrame(
            {"id": range(4), "text": ["HELLO hello 中 é", "excluded record", None, ""]}
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
            check=True,
            capture_output=True,
            text=True,
        )
        restored = json.loads(completed.stdout.strip().splitlines()[-1])
        report = {
            "save": saved,
            "reopen": restored,
            "models": ["BPE", "Unigram"],
            "source_row_ids": [0, 2, 3],
        }
        (args.output / "training-native.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
