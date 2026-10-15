"""Native pair-grid diagonals, source picking, profile/pair links and shared sizing."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui, imgui

from datelier.analysis.types import Algorithm
from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.pipeline import Sort
from scripts.support.input import NativeInput


def main() -> None:
    with TemporaryDirectory(prefix="datelier-pairs-") as directory:
        source = Path(directory) / "matrix.csv"
        source.write_text(
            "x,y,z\n0.0,2.0,1.0\n1.0,0.0,3.0\n2.0,3.0,0.0\n3.0,1.0,2.0\n4.0,4.0,4.0\n"
        )
        original = source.read_bytes()
        native = NativeInput()
        stage = entered = mode = 0
        done = False

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, mode, done
            file = editor.current
            dashboard = file.explorer.active
            data = dashboard.relationships if dashboard else None
            age = evidence.frames - entered
            if evidence.frames > 750:
                raise AssertionError(
                    (stage, mode, file.explorer.message, file.plots.error)
                )
            if native.advance(evidence.frames):
                return
            suffix = None
            if stage == 0 and file.inspection and dashboard:
                file.editor.request(Sort(("x",), True))
                stage, entered = 1, evidence.frames
            elif stage == 1 and not file.editor.busy and dashboard:
                file.plots.relationship_features = ["x", "y", "z"]
                editor.choose_route("Correlations")
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 5:
                suffix = ("correlations", "mode", "value")
            elif stage == 3 and age > 5:
                imgui.get_io().add_key_event(imgui.Key.end, True)
                stage, entered = 4, evidence.frames
            elif stage == 4 and age > 2:
                imgui.get_io().add_key_event(imgui.Key.end, False)
                imgui.get_io().add_key_event(imgui.Key.enter, True)
                stage, entered = 5, evidence.frames
            elif stage == 5 and age > 2:
                imgui.get_io().add_key_event(imgui.Key.enter, False)
                stage, entered = 6, evidence.frames
            elif stage == 6 and age > 5:
                assert file.views.relationship_mode == 1
                suffix = ("0-1", "input", "point")
            elif stage == 7 and file.selection.row_ids:
                assert file.selection.row_ids == {2} and file.table.target_row == 3
                suffix = ("correlations", "expand")
            elif stage == 8 and age > 5:
                suffix = ("correlations", "restore")
            elif stage == 9 and data and data.diagonal_mode == mode and age > 5:
                assert native.find(probe, ("0-0", "plot")) is not None
                if mode < 4:
                    mode += 1
                    file.plots.diagonal_mode = mode
                    entered = evidence.frames
                else:
                    suffix = ("0-0", "plot")
            elif stage == 10 and age > 5:
                assert file.views.tab == "Profiles" and file.profiles.selected == ("x",)
                editor.choose_route("Correlations")
                file.analysis.choose_source(Algorithm.UMAP)
                file.plots.choose_chart("Scatter 3D")
                imgui.get_io().mouse_double_click_time = 1.0
                imgui.get_io().mouse_single_click_delay = 1.1
                stage, entered = 11, evidence.frames
            elif stage == 11 and data and age > 5:
                suffix = ("0-1", "plot")
            elif stage == 12 and age > 2:
                suffix = ("0-1", "plot")
            elif stage == 13 and age > 5:
                assert (
                    file.views.tab == "Relationships" and file.analysis.source is None
                )
                assert not file.plots.three_d and file.plots.custom_scatter
                assert (
                    file.plots.numeric[file.plots.x_index] == "y"
                    and file.plots.numeric[file.plots.y_index] == "x"
                )
                assert (
                    source.read_bytes() == original and not file.analysis.jobs.results
                )
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix and native.click(probe, suffix, evidence.frames):
                stage, entered = stage + 1, evidence.frames

        evidence = run_gui(initial_path=source, on_probe_frame=frame)
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_matrix_mode_keyboard": True,
            "five_diagonal_modes": True,
            "native_original_sorted_row_picking": True,
            "native_expand_restore": True,
            "native_diagonal_profile_link": True,
            "native_pair_raw_2d_link": True,
            "source_preserved": True,
            "implicit_analysis": False,
        }
        Path("/tmp/datelier-rebuild-pairs.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
