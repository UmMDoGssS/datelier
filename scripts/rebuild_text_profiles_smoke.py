"""Native explicit corpus profiling, shared subview sizing and tokenizer training."""

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui

from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.text.types import (
    CorpusMode,
    TextScope,
    TokenMode,
    TrainingSettings,
)


def main() -> None:
    with TemporaryDirectory(prefix="datelier-rebuild-text-") as directory:
        root = Path(directory)
        source, output = root / "corpus.csv", root / "tokenizer.json"
        pl.DataFrame({"body": ["a a b", "b c", "", None, "a"]}).write_csv(source)
        original = source.read_bytes()
        stage, entered, click_stage, next_stage = 0, 0, 0, 0
        clicking: tuple[float, float] | None = None
        done = False

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, click_stage, next_stage, clicking, done
            file, io = editor.current, imgui.get_io()
            age = evidence.frames - entered
            if evidence.frames > 650:
                raise AssertionError(
                    (stage, file.text.corpus.message, file.profiles.family)
                )
            if clicking:
                io.mouse_pos = imgui.ImVec2(*clicking)
                io.want_set_mouse_pos = True
                if age < 4:
                    return
                if click_stage == 0:
                    io.add_mouse_button_event(0, True)
                    click_stage, entered = 1, evidence.frames
                elif click_stage == 1:
                    io.add_mouse_button_event(0, False)
                    click_stage, entered = 2, evidence.frames
                else:
                    clicking = None
                    stage, entered = next_stage, evidence.frames
                return
            suffix: tuple[str, ...] | None = None
            if stage == 0 and file.inspection:
                assert not file.text.corpus.busy and file.text.corpus.profile is None
                file.profiles.choose(("body",))
                file.profiles.text = True
                file.text.jobs.settings = replace(
                    file.text.jobs.settings, scope=TextScope(CorpusMode.COLLECTION)
                )
                editor.choose_route("Profiles")
                stage, entered = 1, evidence.frames
            elif stage == 1 and age > 5:
                suffix, next_stage = ("text-profile-settings", "profile", "run"), 2
            elif (
                stage == 2
                and not file.text.corpus.busy
                and file.text.corpus.profile is None
                and age > 15
            ):
                stage, entered = 1, evidence.frames
            elif stage == 2 and file.text.corpus.profile:
                profile = file.text.corpus.profile.profile
                assert (
                    profile.tokens == 6
                    and profile.documents == 4
                    and profile.nulls == 1
                )
                suffix, next_stage = ("Length distribution", "tab"), 3
            elif stage == 3 and age > 5:
                assert file.text.profile_tab == "Length distribution"
                suffix, next_stage = ("Token frequencies", "tab"), 4
            elif stage == 4 and age > 5:
                assert file.text.profile_tab == "Token frequencies"
                assert file.inspection
                file.selection.choose(file.inspection.dataset.revision, (0,))
                file.text.jobs.settings = replace(
                    file.text.jobs.settings,
                    scope=TextScope(CorpusMode.SELECTION),
                    training=TrainingSettings(
                        TokenMode.BPE,
                        vocabulary_size=16,
                        min_frequency=1,
                        output_path=str(output),
                    ),
                )
                stage, entered = 5, evidence.frames
            elif stage == 5 and age > 5:
                suffix, next_stage = ("train", "toggle"), 6
            elif stage == 6 and age > 5:
                suffix, next_stage = ("training", "train", "run"), 7
            elif stage == 7:
                editor.choose_route("Correlations")
                stage, entered = 8, evidence.frames
            elif stage == 8 and file.text.jobs.settings.tokens.artifact:
                artifact = file.text.jobs.settings.tokens.artifact
                assert artifact.provenance_path and artifact.mode == TokenMode.BPE
                provenance = json.loads(Path(artifact.provenance_path).read_text())
                assert provenance["source_row_ids"] == [0]
                assert (
                    file.views.tab == "Correlations" and source.read_bytes() == original
                )
                assert not editor.playback.snapshot.request
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix:
                point = next(
                    (
                        value
                        for key, value in probe.targets.items()
                        if key.path[-len(suffix) :] == suffix
                    ),
                    None,
                )
                if point:
                    assert point[1] < 760, (suffix, point)
                    io.mouse_pos = imgui.ImVec2(*point)
                    io.want_set_mouse_pos = True
                    clicking, click_stage, entered = point, 0, evidence.frames

        evidence = run_gui(initial_path=source, on_probe_frame=frame)
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_exact_corpus": True,
            "native_profile_subtabs": True,
            "native_selected_training": True,
            "training_provenance": True,
            "source_preserved": True,
            "implicit_playback": 0,
        }
        Path("/tmp/datelier-rebuild-text-profiles.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
