"""Live raw 3D identity, picking, brushing and camera-gesture acceptance."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import patch

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui, implot3d
from numpy.typing import NDArray

from datelier.gui import GuiSession, InspectionEvidence, run_gui
from datelier.gui_scatter3d import Scatter3DView
from datelier.gui_table import TableView
from datelier.operations import Sort
from datelier.plotting import Scatter
from datelier.selection import LinkedSelection


def main() -> None:
    stage, entered = 0, 0
    target = (0.0, 0.0)
    baseline = (0.0, 0.0)
    chosen = -1
    camera: tuple[float, ...] = ()
    ranges: tuple[float, ...] = ()
    camera_before: tuple[float, ...] = ()
    ranges_before: tuple[float, ...] = ()
    original_interact = Scatter3DView._interact

    def record_camera(
        self: Scatter3DView,
        points: Scatter,
        selection: LinkedSelection,
        table: TableView,
    ) -> None:
        nonlocal camera, ranges
        original_interact(self, points, selection, table)
        plot = implot3d.internal.get_current_plot()
        q, lo, hi = plot.rotation, plot.range_min(), plot.range_max()
        camera = (q.x, q.y, q.z, q.w)
        ranges = (lo.x, lo.y, lo.z, hi.x, hi.y, hi.z)

    with TemporaryDirectory(prefix="datelier-3d-") as folder:
        source = Path(folder) / "data.parquet"
        rng = np.random.default_rng(7)
        pl.DataFrame(
            {"x": range(20), "y": rng.normal(size=20), "z": rng.normal(size=20)}
        ).write_parquet(source)
        original = source.read_bytes()

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, entered, target, baseline, chosen
            nonlocal camera_before, ranges_before
            active, dashboard = session.loader.active, session.explorer.active
            if active is None or dashboard is None or session.editor.busy:
                return
            view = session.exploration.scatter3d
            age = evidence.frames - entered
            io = imgui.get_io()
            if stage == 0:
                session.editor.request(Sort(("x",), descending=True))
                stage = 1
            elif stage == 1 and active.first_page.row_ids[0] == 19:
                session.plots.three_d = session.plots.custom_scatter = True
                session.plots.x_index, session.plots.y_index, session.plots.z_index = (
                    0,
                    1,
                    2,
                )
                session.explorer.request(active.dataset, session.plots.settings())
                session.exploration.tab = "Scatter"
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 20 and view.frames > 10:
                points = dashboard.scatters[0]
                assert points.z is not None
                chosen = int(points.row_ids[len(points.x) // 2])
                target = view.point_pixel
                io.mouse_pos = imgui.ImVec2(*target)
                io.want_set_mouse_pos = True
                stage, entered = 3, evidence.frames
            elif stage == 3 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 4, evidence.frames
            elif stage == 4 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 5, evidence.frames
            elif stage == 5 and age > 10:
                assert session.selection.row_ids == {chosen}, (
                    session.selection.row_ids,
                    chosen,
                    target,
                )
                assert view.selected_points == 1
                target = view.point_pixel
                io.add_key_event(imgui.Key.mod_shift, True)
                io.mouse_pos = imgui.ImVec2(target[0] - 4, target[1] - 4)
                io.want_set_mouse_pos = True
                stage, entered = 6, evidence.frames
            elif stage == 6 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 7, evidence.frames
            elif stage == 7 and age > 3:
                io.mouse_pos = imgui.ImVec2(target[0] + 4, target[1] + 4)
                io.want_set_mouse_pos = True
                stage, entered = 8, evidence.frames
            elif stage == 8 and age > 3:
                io.add_mouse_button_event(0, False)
                io.add_key_event(imgui.Key.mod_shift, False)
                stage, entered = 9, evidence.frames
            elif stage == 9 and age > 10:
                assert chosen in session.selection.row_ids
                baseline = view.point_pixel
                camera_before, ranges_before = camera, ranges
                target = view.center_pixel
                io.mouse_pos = imgui.ImVec2(*target)
                io.want_set_mouse_pos = True
                stage, entered = 10, evidence.frames
            elif stage == 10 and age > 3:
                io.add_mouse_button_event(1, True)
                stage, entered = 11, evidence.frames
            elif stage == 11 and age > 3:
                io.mouse_pos = imgui.ImVec2(target[0] + 30, target[1] + 15)
                io.want_set_mouse_pos = True
                stage, entered = 12, evidence.frames
            elif stage == 12 and age > 3:
                io.add_mouse_button_event(1, False)
                stage, entered = 13, evidence.frames
            elif stage == 13 and age > 15:
                assert view.point_pixel != baseline, (
                    view.point_pixel,
                    baseline,
                    "rotation",
                )
                assert chosen in session.selection.row_ids
                assert not np.allclose(camera, camera_before)
                np.testing.assert_allclose(ranges, ranges_before)
                baseline = view.point_pixel
                io.mouse_pos = imgui.ImVec2(*view.center_pixel)
                io.want_set_mouse_pos = True
                stage, entered = 14, evidence.frames
            elif stage == 14 and age > 3:
                io.add_mouse_wheel_event(0, 2)
                stage, entered = 15, evidence.frames
            elif stage == 15 and age > 15:
                assert view.point_pixel != baseline, (
                    view.point_pixel,
                    baseline,
                    "zoom",
                )
                baseline = view.point_pixel
                camera_before, ranges_before = camera, ranges
                target = view.center_pixel
                io.mouse_pos = imgui.ImVec2(*target)
                io.want_set_mouse_pos = True
                io.add_mouse_button_event(0, True)
                stage, entered = 16, evidence.frames
            elif stage == 16 and age > 3:
                io.mouse_pos = imgui.ImVec2(target[0] + 15, target[1] + 10)
                io.want_set_mouse_pos = True
                stage, entered = 17, evidence.frames
            elif stage == 17 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 18, evidence.frames
            elif stage == 18 and age > 15:
                assert view.point_pixel != baseline, (view.point_pixel, baseline, "pan")
                np.testing.assert_allclose(camera, camera_before)
                assert not np.allclose(ranges, ranges_before)
                assert source.read_bytes() == original
                hello_imgui.get_runner_params().app_shall_exit = True

        with patch.object(Scatter3DView, "_interact", record_camera):
            evidence = run_gui(source, smoke_frames=2500, on_frame=frame)
        assert stage == 18
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        h, w = pixels.shape[:2]
        Path("/tmp/datelier-scatter3d.ppm").write_bytes(
            f"P6\n{w} {h}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        print(
            json.dumps(
                {
                    "frames": evidence.frames,
                    "sorted_identity": True,
                    "projected_pick": True,
                    "shift_brush": True,
                    "rotation": True,
                    "wheel_zoom": True,
                    "left_pan": True,
                }
            )
        )


if __name__ == "__main__":
    main()
