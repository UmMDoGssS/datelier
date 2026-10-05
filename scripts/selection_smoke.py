"""Live input-event gate for sampled row links, plot zoom, pan, and brushing."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import numpy as np
from imgui_bundle import hello_imgui, imgui
from numpy.typing import NDArray

from datelier.gui import GuiSession, InspectionEvidence, run_gui
from datelier.pipeline.operations import Comparison, Filter, Sort


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-selection.ppm")
    )
    parser.add_argument("--nonlinear", action="store_true")
    args = parser.parse_args()
    stage, entered = 0, 0
    baseline = (0.0, 0.0, 0.0, 0.0)
    mouse_target = (0.0, 0.0)
    table_id: int | None = None
    axes_changed = False
    with TemporaryDirectory(prefix="datelier-selection-") as directory:
        source = Path(directory) / "source.csv"
        source.write_text("x,y\n" + "".join(f"{i},{i}\n" for i in range(20)))
        original = source.read_bytes()

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, entered, baseline, mouse_target, table_id
            nonlocal axes_changed
            active, dashboard = session.loader.active, session.explorer.active
            if active is None or dashboard is None or session.editor.busy:
                return
            io = imgui.get_io()
            interaction = session.exploration.interaction
            age = evidence.frames - entered
            if stage == 0:
                session.editor.request(Sort(("x",), descending=True))
                stage = 1
            elif stage == 1 and active.first_page.row_ids[0] == 19:
                session.editor.request(Filter("x", Comparison.GE, 5))
                stage = 2
            elif stage == 2 and active.row_count == 15:
                session.plots.point_limit = 4
                session.explorer.request(active.dataset, session.plots.settings())
                session.exploration.tab = "Scatter"
                stage, entered = 3, evidence.frames
            elif stage == 3 and age > 10:
                if args.nonlinear and not axes_changed:
                    axes = session.exploration.scatter_area.axes
                    axes.draft = [[1, 20], [1, 20]]
                    axes.draft_scales = [2, 1]
                    axes.accept()
                    axes_changed, entered = True, evidence.frames
                    return
                assert dashboard.scatters[0].row_ids.tolist() == [19, 15, 10, 5]
                mouse_target = interaction.point_pixel
                io.mouse_pos = imgui.ImVec2(*mouse_target)
                io.want_set_mouse_pos = True
                stage, entered = 4, evidence.frames
            elif stage == 4 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 5, evidence.frames
            elif stage == 5 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 6, evidence.frames
            elif stage == 6 and age > 10:
                assert session.selection.row_ids == {10}, session.selection.row_ids
                assert session.table.selected_visible_rows > 0
                assert interaction.selected_points == 1
                table_id = 10
                mouse_target = session.table.row_pixels[table_id]
                session.selection.choose(active.dataset.revision, ())
                io.mouse_pos = imgui.ImVec2(*mouse_target)
                io.want_set_mouse_pos = True
                stage, entered = 7, evidence.frames
            elif stage == 7 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 8, evidence.frames
            elif stage == 8 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 9, evidence.frames
            elif stage == 9 and age > 10:
                assert session.selection.row_ids == {table_id}, (
                    session.selection.row_ids
                )
                assert interaction.selected_points == 1
                baseline = interaction.limits
                io.mouse_pos = imgui.ImVec2(*interaction.center_pixel)
                io.want_set_mouse_pos = True
                stage, entered = 10, evidence.frames
            elif stage == 10 and age > 3:
                io.add_mouse_wheel_event(0, 2)
                stage, entered = 11, evidence.frames
            elif stage == 11 and age > 10:
                limits = interaction.limits
                assert limits[1] - limits[0] < baseline[1] - baseline[0], (
                    limits,
                    baseline,
                )
                baseline = limits
                mouse_target = interaction.center_pixel
                io.add_mouse_button_event(2, True)
                stage, entered = 12, evidence.frames
            elif stage == 12 and age > 3:
                io.mouse_pos = imgui.ImVec2(mouse_target[0] + 30, mouse_target[1] + 10)
                io.want_set_mouse_pos = True
                stage, entered = 13, evidence.frames
            elif stage == 13 and age > 3:
                io.add_mouse_button_event(2, False)
                stage, entered = 14, evidence.frames
            elif stage == 14 and age > 35:
                assert interaction.limits[0] != baseline[0], (
                    interaction.limits,
                    baseline,
                )
                mouse_target = interaction.point_pixel
                io.add_key_event(imgui.Key.mod_shift, True)
                io.mouse_pos = imgui.ImVec2(mouse_target[0] - 10, mouse_target[1] - 10)
                io.want_set_mouse_pos = True
                stage, entered = 15, evidence.frames
            elif stage == 15 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 16, evidence.frames
            elif stage == 16 and age > 3:
                io.mouse_pos = imgui.ImVec2(mouse_target[0] + 10, mouse_target[1] + 10)
                io.want_set_mouse_pos = True
                stage, entered = 17, evidence.frames
            elif stage == 17 and age > 3:
                io.add_mouse_button_event(0, False)
                io.add_key_event(imgui.Key.mod_shift, False)
                stage, entered = 18, evidence.frames
            elif stage == 18 and age > 10:
                assert session.selection.row_ids == {10}, session.selection.row_ids
                assert interaction.selected_points == 1
                session.exploration.fit = True
                stage, entered = 19, evidence.frames
            elif stage == 19 and age > 30:
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(source, smoke_frames=1500, on_frame=frame)
        assert stage == 19 and source.read_bytes() == original
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        height, width = pixels.shape[:2]
        args.output.write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        report = {
            "frames": evidence.frames,
            "sort_filter_sample_identity": True,
            "plot_to_table": True,
            "table_to_plot": True,
            "wheel_zoom": True,
            "middle_pan": True,
            "shift_brush": True,
            "source_preserved": True,
            "input": "Dear ImGui mouse/key events and backend cursor positioning",
            "nonlinear_axes": args.nonlinear,
        }
        args.output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
