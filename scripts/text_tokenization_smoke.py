"""Native normalization/preparation/reload and fresh-process text restoration."""

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
from tokenizers import Tokenizer, models, normalizers, pre_tokenizers, trainers

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.inspection.text.tokenization import import_tokenizer
from datelier.inspection.text.types import (
    Normalization,
    TextSettings,
    TextSource,
    TokenMode,
    TokenSettings,
)


def run(root: Path, *, restore: bool, output: Path) -> dict[str, object]:
    stage = entered = 0
    pixels: dict[str, tuple[float, float]] = {}
    original_button, original_checkbox = imgui.button, imgui.checkbox
    original_header = imgui.collapsing_header
    workspace = root / "session.datelier.json"
    path = root / "local.json"

    def capture(label: str) -> None:
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        pixels[label] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)

    def button(label: str, size: imgui.ImVec2 | None = None) -> bool:
        result = original_button(label, size)
        if label in ("Prepare text record", "Reload saved tokenizer"):
            capture(label)
        return result

    def checkbox(label: str, checked: bool) -> tuple[bool, bool]:
        result = original_checkbox(label, checked)
        if label == "Lowercase tokens":
            capture(label)
        return result

    def header(label: str, flags: int = 0) -> bool:
        result = original_header(label, flags)
        if label == "Text settings":
            capture(label)
        return result

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered
        file = editor.active
        if file.loader.active is None:
            if restore:
                ready = next((f for f in editor.files if f.loader.active), None)
                if ready:
                    editor.activate(ready.identity)
            return
        jobs = file.text.jobs
        io = imgui.get_io()
        age = evidence.frames - entered

        def click(label: str, next_stage: int) -> None:
            nonlocal stage, entered
            io.mouse_pos = imgui.ImVec2(*pixels[label])
            io.want_set_mouse_pos = True
            stage, entered = next_stage, evidence.frames

        if stage == 0:
            hello_imgui.get_runner_params().docking_params.focus_dockable_window("Text")
            if restore:
                assert jobs.settings.tokens.mode == TokenMode.BPE
                assert jobs.settings.tokens.lowercase
                assert (
                    jobs.settings.tokens.artifact
                    and not jobs.busy
                    and jobs.active is None
                )
                stage, entered = 20, evidence.frames
            else:
                jobs.settings = TextSettings(
                    "text",
                    TextSource.INLINE,
                    tokens=TokenSettings(TokenMode.CHARACTER, Normalization.NFC),
                )
                stage, entered = 1, evidence.frames
        elif stage == 1 and age > 10 and "Text settings" in pixels:
            click("Text settings", 2)
        elif stage in (2, 5, 8, 11, 16, 21, 25) and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = stage + 1, evidence.frames
        elif stage in (3, 6, 9, 12, 17, 22, 26) and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = stage + 1, evidence.frames
        elif stage == 4 and "Lowercase tokens" in pixels and age > 5:
            click("Lowercase tokens", 5)
        elif stage == 7 and jobs.settings.tokens.lowercase and age > 5:
            click("Text settings", 8)
        elif stage == 10 and age > 5:
            click("Prepare text record", 11)
        elif stage == 13 and jobs.active and file.text.shown:
            result = jobs.active
            assert result.normalized == "hello é 中🙂"
            assert any(
                result.document.text[t.start : t.end] == "e\u0301"
                for t in result.tokens
            )
            reference = import_tokenizer(path)
            jobs.settings = replace(
                jobs.settings,
                tokens=replace(
                    jobs.settings.tokens, mode=TokenMode.BPE, artifact=reference
                ),
            )
            stage, entered = 15, evidence.frames
        elif stage == 15 and age > 5 and "Reload saved tokenizer" in pixels:
            click("Reload saved tokenizer", 16)
        elif stage == 18 and jobs.message.startswith("Loaded local BPE"):
            editor.save_workspace(workspace)
            stage = 19
        elif stage == 19 and editor.workspace_jobs.saved:
            hello_imgui.get_runner_params().app_shall_exit = True
        elif stage == 20 and age > 10:
            path.rename(root / "missing.json")
            click("Prepare text record", 21)
        elif stage == 23 and "Cannot prepare text" in jobs.message:
            assert not jobs.busy and jobs.active is None
            (root / "missing.json").rename(path)
            stage, entered = 24, evidence.frames
        elif stage == 24 and age > 6:
            click("Reload saved tokenizer", 25)
        elif stage == 27 and jobs.message.startswith("Loaded local BPE"):
            jobs.request_document()
            stage = 28
        elif stage == 28 and jobs.active and file.text.shown:
            assert jobs.active.normalized == "hello é 中🙂"
            assert jobs.active.document.origin.file_id == file.identity
            hello_imgui.get_runner_params().app_shall_exit = True

    with (
        patch.object(imgui, "button", side_effect=button),
        patch.object(imgui, "checkbox", side_effect=checkbox),
        patch.object(imgui, "collapsing_header", side_effect=header),
    ):
        evidence = run_gui(
            None if restore else root / "source.csv",
            initial_workspace=workspace if restore else None,
            smoke_frames=320,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    output.mkdir(parents=True, exist_ok=True)
    screenshot = output / (
        "tokenizer-restore.png" if restore else "tokenizer-controls.png"
    )
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        screenshot
    )
    assert stage == (28 if restore else 19), (stage, pixels)
    return {
        "frames": evidence.frames,
        "restore": restore,
        "stage": stage,
        "screenshot": str(screenshot),
        "implicit_work_on_restore": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-text-native")
    )
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, restore=True, output=args.output)))
        return
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "source.csv").write_text(
            "id,text\n1,HELLO e\u0301 中🙂\n2,second document\n"
        )
        tokenizer = Tokenizer(models.BPE(unk_token="[UNK]"))
        tokenizer.normalizer = normalizers.NFC()
        tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
        tokenizer.train_from_iterator(
            ["hello é 中🙂", "second document"],
            trainer=trainers.BpeTrainer(vocab_size=50, special_tokens=["[UNK]"]),
        )
        tokenizer.save(str(root / "local.json"))
        first = run(root, restore=False, output=args.output)
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
        report = {"save": first, "reopen": restored}
        (args.output / "tokenizer-native.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
