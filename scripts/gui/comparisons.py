"""Native shared source selectors, explicit comparison apply, resize and row links."""

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui, imgui

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.comparison_settings import Normalization
from datelier.pipeline import Sort
from scripts.support.input import NativeInput


def main() -> None:
    with TemporaryDirectory(prefix="datelier-rebuild-comparisons-") as directory:
        root = Path(directory)
        first_path, second_path = root / "train.csv", root / "test.csv"
        first_path.write_text("x,kind\n3.0,a\n0.0,b\n2.0,a\n1.0,b\n")
        second_path.write_text("different,category\n0.0,b\n3.0,b\n")
        originals = first_path.read_bytes(), second_path.read_bytes()
        inputs, stage, entered, done = NativeInput(), 0, 0, False
        first_id = second_id = ""

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, done, first_id, second_id
            model = editor.compare.columns
            age = evidence.frames - entered
            if evidence.frames > 650:
                raise AssertionError(
                    (stage, model.message, model.jobs.selection_message)
                )
            if inputs.advance(evidence.frames):
                return
            suffix: tuple[str, ...] | None = None
            if stage == 0 and editor.active.inspection:
                first_id = editor.active_id
                editor.active.editor.request(Sort(("x",)))
                second_id = editor.new_file(second_path).identity
                stage, entered = 1, evidence.frames
            elif (
                stage == 1
                and len(editor.files) == 2
                and all(f.inspection and not f.editor.busy for f in editor.files)
            ):
                editor.choose_route("Compare files")
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
                model.draft = replace(
                    model.draft, bins=2, normalization=Normalization.COUNT
                )
                stage, entered = 6, evidence.frames
            elif stage == 6 and age > 5:
                suffix = ("recipe-controls", "apply", "run")
            elif stage == 7 and model.active:
                assert model.active.series[0].counts.tolist() == [2, 2]
                assert model.active.series[1].counts.tolist() == [1, 1]
                assert editor.navigation.comparing and editor.active_id == second_id
                suffix = ("column-viewport", "expand")
            elif stage == 8 and age > 5:
                suffix = ("column-viewport", "restore")
            elif stage == 9 and age > 5:
                model.draft = replace(model.draft, bins=5)
                editor.activate(first_id)
                stage, entered = 10, evidence.frames
            elif stage == 10 and age > 5:
                assert not editor.navigation.comparing and model.draft.bins == 5
                editor.choose_route("Compare files")
                stage, entered = 11, evidence.frames
            elif stage == 11 and age > 5:
                assert model.active and model.active.settings.bins == 2
                suffix = ("column-chart", "canvas")
            elif stage == 12 and editor.active.selection.row_ids:
                assert editor.active_id == first_id and not editor.navigation.comparing
                assert editor.active.selection.row_ids in ({1, 3}, {0, 2})
                assert editor.active.table.jump or editor.active.table.target_row in (
                    1,
                    3,
                )
                editor.choose_route("Compare files")
                model.draft = replace(
                    model.draft,
                    sources=tuple(
                        replace(
                            s, column="kind" if s.file_id == first_id else "category"
                        )
                        for s in model.draft.sources
                    ),
                )
                stage, entered = 13, evidence.frames
            elif stage == 13 and age > 5:
                suffix = ("recipe-controls", "apply", "run")
            elif stage == 14 and model.active and model.active.labels:
                assert set(model.active.keys) == {"a", "b"}
                assert originals == (first_path.read_bytes(), second_path.read_bytes())
                assert all(
                    not f.analysis.jobs.results
                    and f.text.corpus.profile is None
                    and f.images.profile_jobs.active is None
                    and f.audio.collection.active is None
                    for f in editor.all_files
                )
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix and inputs.click(probe, suffix, evidence.frames):
                stage, entered = stage + 1, evidence.frames

        evidence = run_gui(initial_path=first_path, on_probe_frame=frame)
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_shared_file_selector": True,
            "native_explicit_apply": True,
            "numeric_category_comparisons": True,
            "native_expand_restore": True,
            "drafts_survive_file_activation": True,
            "native_linked_original_rows": True,
            "source_preserved": True,
            "implicit_ml_media_corpus": False,
        }
        Path("/tmp/datelier-rebuild-comparisons.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
