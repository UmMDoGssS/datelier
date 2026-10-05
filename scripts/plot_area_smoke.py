"""Real drag/expand events and native axis checks across every chart family."""

import argparse
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import patch

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui, implot3d
from numpy.typing import NDArray

from datelier.gui import GuiSession, InspectionEvidence, run_gui
from datelier.gui_plot_area import PlotArea
from datelier.gui_scatter3d import Scatter3DView
from datelier.gui_table import TableView
from datelier.plotting import Scatter
from datelier.selection import LinkedSelection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--view",
        choices=["Profile", "Comparison", "Scatter", "Scatter3D", "Heatmap", "Grid"],
        default="Scatter",
    )
    parser.add_argument("--source", type=Path)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--expanded", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-plot-area.ppm")
    )
    args = parser.parse_args()
    stage, entered = 0, 0
    baseline_height = 0.0
    baseline_limits = ((0.0, 1.0), (0.0, 1.0))
    area: PlotArea | None = None
    toolbar_drag = False
    camera: tuple[float, ...] = ()
    baseline_camera: tuple[float, ...] = ()
    original_interact = Scatter3DView._interact

    def record_camera(
        self: Scatter3DView,
        points: Scatter,
        selection: LinkedSelection,
        table: TableView,
    ) -> None:
        nonlocal camera
        original_interact(self, points, selection, table)
        plot = implot3d.internal.get_current_plot()
        rotation, lo, hi = plot.rotation, plot.range_min(), plot.range_max()
        camera = (
            rotation.x,
            rotation.y,
            rotation.z,
            rotation.w,
            lo.x,
            lo.y,
            lo.z,
            hi.x,
            hi.y,
            hi.z,
        )

    def limits(
        session: GuiSession, current: PlotArea
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        if args.view == "Grid":
            bounds = session.exploration.relationships.interactions[(0, 1)].limits
            return ((bounds[0], bounds[1]), (bounds[2], bounds[3]))
        return current.axes.limits

    with TemporaryDirectory(prefix="datelier-plot-area-") as folder:
        source = args.source or Path(folder) / "data.parquet"
        if args.source is None:
            rng = np.random.default_rng(5)
            pl.DataFrame(
                {
                    "x": np.arange(60) + 1,
                    "y": rng.normal(size=60),
                    "z": rng.normal(size=60),
                }
            ).write_parquet(source)
        before = sha256(source.read_bytes()).hexdigest()

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, entered, area, toolbar_drag
            nonlocal baseline_height, baseline_limits, baseline_camera
            active, dashboard = session.loader.active, session.explorer.active
            if active is None or dashboard is None:
                return
            view, plots = session.exploration, session.plots
            io = imgui.get_io()
            age = evidence.frames - entered
            if stage == 0:
                hello_imgui.change_window_size((args.width, args.height))
                names = ["age", "fare", "parch"] if args.source else ["x", "y", "z"]
                plots.relationship_features = names[:2]
                plots.x_index, plots.y_index, plots.z_index = map(
                    plots.numeric.index, names
                )
                if args.view in ("Scatter", "Scatter3D"):
                    plots.custom_scatter = True
                    plots.three_d = args.view == "Scatter3D"
                    view.tab = "Scatter"
                    area = view.scatter3d_area if plots.three_d else view.scatter_area
                elif args.view in ("Heatmap", "Grid"):
                    view.tab = "Correlations"
                    view.relationships.mode = int(args.view == "Grid")
                    area = view.relationships.area
                elif args.view == "Comparison":
                    plots.compare_columns = names[:2]
                    view.profile.selection.columns = tuple(names[:2])
                    area = view.profile.area
                else:
                    view.profile_index = plots.columns.index(names[0])
                    view.profile_mode = 2
                    area = view.profile.area
                session.explorer.request(active.dataset, plots.settings())
                stage, entered = 1, evidence.frames
            elif stage == 1 and age > 20:
                assert area is not None and area.rendered_height >= 170
                baseline_height = area.rendered_height
                baseline_camera = camera
                baseline_limits = limits(session, area)
                toolbar_drag = area.resize_pixel[1] >= args.height - 30
                io.mouse_pos = imgui.ImVec2(
                    *(area.height_pixel if toolbar_drag else area.resize_pixel)
                )
                io.want_set_mouse_pos = True
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 3, evidence.frames
            elif stage == 3 and age > 3:
                assert area is not None
                io.mouse_pos = (
                    imgui.ImVec2(area.height_pixel[0] + 20, area.height_pixel[1])
                    if toolbar_drag
                    else imgui.ImVec2(area.resize_pixel[0], area.resize_pixel[1] + 20)
                )
                io.want_set_mouse_pos = True
                stage, entered = 4, evidence.frames
            elif stage == 4 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 5, evidence.frames
            elif stage == 5 and age > 8:
                assert area is not None and area.height >= 170, (
                    area,
                    baseline_height,
                    io.mouse_pos,
                )
                assert abs(area.rendered_height - (baseline_height + 20)) < 2, (
                    baseline_height,
                    area.height,
                    area.rendered_height,
                    area.resize_pixel,
                    io.mouse_pos,
                )
                assert np.allclose(limits(session, area), baseline_limits)
                io.mouse_pos = imgui.ImVec2(*area.expand_pixel)
                io.want_set_mouse_pos = True
                stage, entered = 6, evidence.frames
            elif stage == 6 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 7, evidence.frames
            elif stage == 7 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 8, evidence.frames
            elif stage == 8 and age > 12:
                assert (
                    area is not None and area.expanded and area.rendered_height >= 340
                )
                assert np.allclose(limits(session, area), baseline_limits)
                if args.view == "Scatter3D":
                    assert np.allclose(camera, baseline_camera)
                if args.view in ("Scatter", "Profile", "Comparison"):
                    io.mouse_pos = imgui.ImVec2(*area.axes.open_pixel)
                    io.want_set_mouse_pos = True
                    stage, entered = 9, evidence.frames
                else:
                    stage, entered = 17, evidence.frames
            elif stage == 9 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 10, evidence.frames
            elif stage == 10 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 11, evidence.frames
            elif stage == 11 and age > 5:
                assert area is not None
                profile_plot = args.view in ("Profile", "Comparison")
                area.axes.draft = [
                    [1, 40],
                    [0, 1] if profile_plot else [0, 100] if args.source else [-2, 2],
                ]
                area.axes.draft_scales = [2, 0] if profile_plot else [2, 1]
                io.mouse_pos = imgui.ImVec2(*area.axes.apply_pixel)
                io.want_set_mouse_pos = True
                stage, entered = 12, evidence.frames
            elif stage == 12 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 13, evidence.frames
            elif stage == 13 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 14, evidence.frames
            elif stage == 14 and age > 5:
                assert area is not None
                expected = (
                    (1, 40),
                    (0, 1)
                    if args.view in ("Profile", "Comparison")
                    else (0, 100)
                    if args.source
                    else (-2, 2),
                )
                assert np.allclose(area.axes.limits, expected), area.axes
                if args.view in ("Profile", "Comparison"):
                    assert area.axes.scales == [2, 0]
                    baseline_limits = limits(session, area)
                    stage, entered = 17, evidence.frames
                    return
                io.mouse_pos = imgui.ImVec2(*view.interaction.center_pixel)
                io.want_set_mouse_pos = True
                stage, entered = 15, evidence.frames
            elif stage == 15 and age > 3:
                io.add_mouse_wheel_event(0, 1)
                stage, entered = 16, evidence.frames
            elif stage == 16 and age > 8:
                assert area is not None and area.axes.limits[0] != (1, 40)
                baseline_limits = limits(session, area)
                stage, entered = 17, evidence.frames
            elif stage == 17 and age > 8:
                assert area is not None
                if not args.expanded:
                    area.expanded = False
                stage, entered = 18, evidence.frames
            elif stage == 18 and age > 10:
                assert area is not None
                assert np.allclose(limits(session, area), baseline_limits)
                hello_imgui.get_runner_params().app_shall_exit = True

        with patch.object(Scatter3DView, "_interact", record_camera):
            evidence = run_gui(source, smoke_frames=2000, on_frame=frame)
        assert stage == 18 and area is not None
        assert sha256(source.read_bytes()).hexdigest() == before
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        h, w = pixels.shape[:2]
        args.output.write_bytes(
            f"P6\n{w} {h}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        report = {
            "frames": evidence.frames,
            "view": args.view,
            "size": [args.width, args.height],
            "drag_resize": True,
            "expanded_view": True,
            "view_preserved": True,
            "axis_ranges_and_scales": args.view in ("Scatter", "Profile", "Comparison"),
            "source_preserved": True,
        }
        args.output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
