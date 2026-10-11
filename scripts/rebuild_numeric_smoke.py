"""Native supporting-axis/alias forms, alignment errors and exact record windows."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui, imgui
from rebuild_input import NativeInput, NativeText

from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.arrays.mapping import ArrayLayout
from datelier.pipeline.operations import Sort


def main() -> None:
    with TemporaryDirectory(prefix="datelier-numeric-") as directory:
        source = Path(directory) / "records.npz"
        values = np.arange(60).reshape(3, 4, 5)
        np.savez_compressed(source, values=values, scores=np.arange(6).reshape(2, 3))
        original = source.read_bytes()
        native, text = NativeInput(), NativeText()
        stage = entered = 0
        done = False

        def frame(
            editor: EditorController,
            probe: GuiProbe,
            evidence: InspectionEvidence,
        ) -> None:
            nonlocal stage, entered, done
            file = editor.current
            age = evidence.frames - entered
            if evidence.frames > 1200:
                raise AssertionError(
                    (
                        stage,
                        file.array_records.jobs.message,
                        [k.path for k in probe.targets],
                    )
                )
            if native.advance(evidence.frames) or text.advance(evidence.frames):
                return
            suffix: tuple[str, ...] | None = None
            if stage == 0 and file.arrays.catalog:
                assert file.arrays.active is None
                suffix = ("members", "values", "select")
            elif stage == 1:
                suffix = ("mapping", "open")
            elif stage == 2:
                draft = file.array_source.mapping
                assert draft
                draft.choose_layout(ArrayLayout.GENERIC)
                draft.candidate = ("scores",)
                suffix = ("form", "add", "run")
            elif stage == 3:
                suffix = ("form", "confirm", "run")
            elif stage == 4 and age > 3:
                assert not file.record_views.pending and not file.record_views.files
                assert (
                    file.arrays.active is None
                    and file.arrays.store.temporary_path is None
                )
                suffix = ("supporting", "1", "column", "value")
            elif stage == 5:
                text.start("score", evidence.frames)
                stage, entered = 6, evidence.frames
            elif stage == 6:
                suffix = ("supporting", "1", "axis", "value")
            elif stage == 7 and age > 2:
                imgui.get_io().add_key_event(imgui.Key.end, True)
                stage, entered = 8, evidence.frames
            elif stage == 8 and age > 2:
                imgui.get_io().add_key_event(imgui.Key.end, False)
                imgui.get_io().add_key_event(imgui.Key.enter, True)
                stage, entered = 9, evidence.frames
            elif stage == 9 and age > 2:
                imgui.get_io().add_key_event(imgui.Key.enter, False)
                stage, entered = 10, evidence.frames
            elif stage == 10:
                suffix = ("supporting", "1", "fixed", "value")
            elif stage == 11:
                text.start("1,0", evidence.frames)
                stage, entered = 12, evidence.frames
            elif stage == 12:
                draft = file.array_source.mapping
                assert draft and draft.supports[0].column == "score"
                assert draft.supports[0].record_axis == 1
                assert draft.supports[0].fixed == "1,0"
                suffix = ("form", "confirm", "run")
            elif (
                stage == 13 and editor.current is not editor.active and file.inspection
            ):
                assert file.inspection.dataset.table["score"].to_list() == [3, 4, 5]
                file.editor.request(Sort(("score",), descending=True))
                stage, entered = 14, evidence.frames
            elif stage == 14 and not file.editor.busy and age > 3:
                assert (
                    file.inspection
                    and file.inspection.dataset.row_ids.to_list() == [2, 1, 0]
                )
                file.records.open_position(
                    file.inspection.dataset.revision, 0, 2, "record_index", mapped=True
                )
                stage, entered = 15, evidence.frames
            elif stage == 15 and age > 4:
                suffix = ("slice-settings", "starts", "value")
            elif stage == 16:
                text.start("1,2", evidence.frames)
                stage, entered = 17, evidence.frames
            elif stage == 17:
                suffix = ("slice-settings", "counts", "value")
            elif stage == 18:
                text.start("2,3", evidence.frames)
                stage, entered = 19, evidence.frames
            elif stage == 19:
                suffix = ("slice-settings", "prepare", "run")
            elif stage == 20 and file.array_records.jobs.active:
                prepared = file.array_records.jobs.active
                assert prepared.settings.fixed[0] == 2
                np.testing.assert_array_equal(prepared.raw, values[2, 1:3, 2:5])
                suffix = ("array-plot", "expand")
            elif stage == 21 and age > 4:
                suffix = ("array-plot", "restore")
            elif stage == 22 and age > 4:
                assert source.read_bytes() == original
                assert all(not f.analysis.jobs.results for f in editor.all_files)
                assert not editor.playback.snapshot.request
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix and native.click(probe, suffix, evidence.frames):
                stage, entered = stage + 1, evidence.frames

        evidence = run_gui(initial_path=source, on_probe_frame=frame)
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_supporting_axis_alias_coordinates": True,
            "native_invalid_alignment_no_decoding": True,
            "native_sorted_exact_record_window": True,
            "native_expand_restore": True,
            "source_preserved": True,
            "implicit_analysis_playback": False,
        }
        Path("/tmp/datelier-rebuild-numeric.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
