"""Native 2D/3D source row picking, camera faces, colors and shared view sizing."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui, imgui
from rebuild_input import NativeInput

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.pipeline.operations import Sort


def main() -> None:
    with TemporaryDirectory(prefix="datelier-scatter-") as directory:
        source = Path(directory) / "points.csv"
        source.write_text(
            "x,y,z,color\n0.0,2.0,1.0,0.0\n1.0,0.0,3.0,1.0\n2.0,3.0,0.0,2.0\n3.0,1.0,2.0,3.0\n4.0,4.0,4.0,4.0\n"
        )
        original = source.read_bytes()
        native = NativeInput()
        stage = entered = 0
        done = False

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, done
            file = editor.current
            data = file.explorer.active
            age = evidence.frames - entered
            if evidence.frames > 650:
                raise AssertionError(
                    (
                        stage,
                        file.plots.error,
                        file.explorer.message,
                        file.selection.row_ids,
                    )
                )
            if native.advance(evidence.frames):
                return
            suffix = None
            if stage == 0 and file.inspection and data:
                file.editor.request(Sort(("x",), True))
                stage, entered = 1, evidence.frames
            elif stage == 1 and not file.editor.busy and data:
                editor.choose_relationship_chart("Scatter 3D")
                file.plots.custom_scatter = True
                file.plots.choose_axis("x_index", file.plots.numeric.index("x"))
                file.plots.choose_axis("y_index", file.plots.numeric.index("y"))
                file.plots.choose_axis("z_index", file.plots.numeric.index("z"))
                stage, entered = 2, evidence.frames
            elif (
                stage == 2
                and data
                and data.scatters
                and data.scatters[0].z is not None
                and age > 5
            ):
                suffix = ("scatter3d", "canvas", "input", "point")
            elif stage == 3 and file.selection.row_ids:
                assert file.selection.row_ids == {2} and file.table.target_row == 3
                suffix = ("scatter", "expand")
            elif stage == 4 and age > 5:
                suffix = ("scatter", "restore")
            elif stage == 5 and age > 5:
                suffix = ("scatter3d", "face", "value")
            elif stage == 6 and age > 5:
                imgui.get_io().add_key_event(imgui.Key.end, True)
                stage, entered = 7, evidence.frames
            elif stage == 7 and age > 2:
                imgui.get_io().add_key_event(imgui.Key.end, False)
                imgui.get_io().add_key_event(imgui.Key.enter, True)
                stage, entered = 8, evidence.frames
            elif stage == 8 and age > 2:
                imgui.get_io().add_key_event(imgui.Key.enter, False)
                stage, entered = 9, evidence.frames
            elif stage == 9 and age > 5:
                assert native.find(probe, ("face-Right (YZ)",)) is not None
                if file.loader.revision:
                    file.selection.choose(file.loader.revision, ())
                stage, entered = 10, evidence.frames
            elif stage == 10 and age > 5:
                point = native.find(probe, ("scatter3d", "canvas", "input", "point"))
                assert point
                imgui.get_io().add_key_event(imgui.Key.mod_shift, True)
                native.drag(
                    (point[0] - 12, point[1] - 12),
                    (point[0] + 12, point[1] + 12),
                    evidence.frames,
                )
                stage, entered = 11, evidence.frames
            elif stage == 11 and age > 5 and file.selection.row_ids:
                assert 2 in file.selection.row_ids
                assert file.selection.row_ids.issubset(set(range(5)))
                imgui.get_io().add_key_event(imgui.Key.mod_shift, False)
                file.plots.choose_color("Column")
                file.plots.color_index = file.plots.color_columns.index("color") + 1
                editor.choose_relationship_chart("Scatter 2D")
                file.selection.choose(
                    file.loader.revision, ()
                ) if file.loader.revision else None
                stage, entered = 12, evidence.frames
            elif (
                stage == 12
                and data
                and data.scatters
                and data.scatters[0].z is None
                and data.scatters[0].colors
                and age > 5
            ):
                assert data.scatters[0].colors.scale is not None
                suffix = ("scatter2d", "canvas", "input", "point")
            elif stage == 13 and file.selection.row_ids:
                assert file.selection.row_ids == {2} and file.table.target_row == 3
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
            "native_2d_3d_picking": True,
            "native_projected_brush": True,
            "sorted_original_rows": True,
            "native_expand_restore": True,
            "native_face_keyboard": True,
            "continuous_color_scale": True,
            "source_preserved": True,
            "implicit_analysis": False,
        }
        Path("/tmp/datelier-rebuild-scatter.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
