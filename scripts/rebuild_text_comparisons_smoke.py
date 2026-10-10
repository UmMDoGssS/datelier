"""Native explicit shared text corpus preparation, subtabs, resizing and row links."""

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui, imgui
from rebuild_input import NativeInput

from datelier.application.comparisons.base import ComparisonFamily
from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.text.types import (
    CorpusMode,
    TextScope,
    TokenMode,
    TokenSettings,
)
from datelier.pipeline.operations import Sort


def main() -> None:
    with TemporaryDirectory(prefix="datelier-text-compare-") as directory:
        root = Path(directory)
        first = root / "train.csv"
        second = root / "test.csv"
        first.write_text("body\nB B B\nA\nB B\n")
        second.write_text("text\nA\nB B B\n")
        originals = first.read_bytes(), second.read_bytes()
        native = NativeInput()
        stage = entered = 0
        done = False
        first_id = ""

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, done, first_id
            model = editor.compare.text
            age = evidence.frames - entered
            if evidence.frames > 750:
                raise AssertionError(
                    (stage, model.message, model.jobs.selection_message)
                )
            if native.advance(evidence.frames):
                return
            suffix = None
            if stage == 0 and editor.active.inspection:
                first_id = editor.active_id
                editor.active.editor.request(Sort(("body",)))
                editor.new_file(second)
                stage, entered = 1, evidence.frames
            elif (
                stage == 1
                and len(editor.files) == 2
                and all(f.inspection and not f.editor.busy for f in editor.files)
            ):
                editor.choose_route("Compare files")
                editor.compare.tab = ComparisonFamily.TEXT
                editor.current.text.jobs.settings = replace(
                    editor.current.text.jobs.settings,
                    tokens=TokenSettings(TokenMode.WHITESPACE, lowercase=True),
                )
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 5:
                suffix = ("contributors", "files", "open")
            elif stage == 3 and age > 5:
                suffix = ("files", "list", "bulk")
            elif stage == 4 and age > 5:
                assert len(model.draft.sources) == 2 and model.jobs.started == 0
                imgui.get_io().add_key_event(imgui.Key.escape, True)
                stage, entered = 5, evidence.frames
            elif stage == 5:
                imgui.get_io().add_key_event(imgui.Key.escape, False)
                for mapping in model.draft.sources:
                    model.update_mapping(
                        replace(mapping, scope=TextScope(CorpusMode.COLLECTION))
                    )
                model.draft = replace(model.draft, bins=3)
                stage, entered = 6, evidence.frames
            elif stage == 6 and age > 5:
                suffix = ("text-comparison-tools", "copy-tokenizer", "run")
            elif stage == 7 and age > 5:
                assert model.draft.tokens.lowercase
                suffix = ("recipe-controls", "apply", "run")
            elif stage == 8 and model.active and age > 5:
                assert [p.tokens for p in model.active.profiles] == [6, 4]
                assert set(model.active.frequencies["piece"]) == {"a", "b"}
                assert editor.navigation.comparing
                suffix = ("text-length-viewport", "expand")
            elif stage == 9 and age > 5:
                suffix = ("text-length-viewport", "restore")
            elif stage == 10 and age > 5:
                suffix = ("Statistics", "tab")
            elif stage == 11 and age > 5:
                suffix = ("Token frequencies", "tab")
            elif stage == 12 and age > 5:
                if model.view.tab != "Token frequencies":
                    if native.click(
                        probe, ("Token frequencies", "tab"), evidence.frames
                    ):
                        entered = evidence.frames
                    return
                suffix = ("text-frequency-viewport", "expand")
            elif stage == 13 and age > 5:
                suffix = ("text-frequency-viewport", "restore")
            elif stage == 14 and age > 5:
                suffix = ("Record outcomes", "tab")
            elif stage == 15 and age > 5:
                suffix = ("Lengths", "tab")
            elif stage == 16 and age > 5:
                if model.view.tab != "Lengths":
                    if native.click(probe, ("Lengths", "tab"), evidence.frames):
                        entered = evidence.frames
                    return
                suffix = ("text-length-chart", "canvas")
            elif stage == 17 and editor.current.selection.row_ids:
                assert editor.active_id == first_id and not editor.navigation.comparing
                assert editor.current.selection.row_ids == {1}, (
                    editor.current.selection.row_ids
                )
                assert originals == (first.read_bytes(), second.read_bytes())
                assert all(
                    f.text.corpus.profile is None
                    and not f.text.jobs.settings.tokens.artifact
                    for f in editor.all_files
                )
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix and native.click(probe, suffix, evidence.frames):
                stage, entered = stage + 1, evidence.frames

        evidence = run_gui(initial_path=first, on_probe_frame=frame)
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_shared_contributor_selector": True,
            "explicit_prepare": True,
            "copy_active_tokenizer": True,
            "statistics_frequencies_outcomes": True,
            "expand_restore_both_charts": True,
            "original_sorted_rows_linked": True,
            "source_preserved": True,
            "implicit_training_corpus": False,
        }
        Path("/tmp/datelier-rebuild-text-comparisons.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
