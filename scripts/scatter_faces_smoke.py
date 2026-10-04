"""Real 3D face-menu clicks, projected planes, free rotation and expanded views."""

import argparse
import json
from hashlib import sha256
from math import radians, sqrt
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import patch

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui, implot3d
from numpy.typing import NDArray

from datelier.analysis_types import Algorithm
from datelier.gui import GuiSession, InspectionEvidence, run_gui
from datelier.gui_scatter3d import FACE_VIEWS, Scatter3DView
from datelier.gui_table import TableView
from datelier.plotting import Scatter
from datelier.selection import LinkedSelection


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--embedding", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("/tmp/datelier-faces.ppm"))
    args = parser.parse_args()
    stage, entered, face_index = 0, 0, 0
    chosen = -1
    menu_pixel = (0.0, 0.0)
    item_pixels: dict[str, tuple[float, float]] = {}
    rotation: tuple[float, ...] = ()
    ranges: tuple[float, ...] = ()
    baseline_ranges: tuple[float, ...] = ()
    baseline_rotation: tuple[float, ...] = ()
    axis_pixels: list[tuple[float, float]] = []
    ray_direction: tuple[float, float, float] = (0, 0, 0)
    unlocked = False
    faces = list(FACE_VIEWS)
    button, selectable, interact = (
        imgui.button,
        imgui.selectable,
        Scatter3DView._interact,
    )

    def center() -> tuple[float, float]:
        pos, size = imgui.get_item_rect_min(), imgui.get_item_rect_size()
        return (pos.x + size.x / 2, pos.y + size.y / 2)

    def record_button(
        label: str, size: imgui.ImVec2 | tuple[float, float] = (0, 0)
    ) -> bool:
        nonlocal menu_pixel
        clicked = button(label, size)
        if label == "View face":
            menu_pixel = center()
        return clicked

    def record_item(label: str, selected: bool = False) -> tuple[bool, bool]:
        result = selectable(label, selected)
        if label in FACE_VIEWS:
            item_pixels[label] = center()
        return result

    def record_camera(
        self: Scatter3DView,
        points: Scatter,
        selection: LinkedSelection,
        table: TableView,
    ) -> None:
        nonlocal rotation, ranges, axis_pixels, unlocked, ray_direction
        interact(self, points, selection, table)
        plot = implot3d.internal.get_current_plot()
        q, lo, hi = plot.rotation, plot.range_min(), plot.range_max()
        rotation = (q.x, q.y, q.z, q.w)
        ranges = (lo.x, lo.y, lo.z, hi.x, hi.y, hi.z)
        unlocked = not plot.rotation_cond
        ray = implot3d.pixels_to_plot_ray(*self.center_pixel)
        # Compare in normalized plot-box space; source columns have different
        # units/ranges, which amplify native angle rounding in data-space rays.
        dx = ray.direction.x / (hi.x - lo.x)
        dy = ray.direction.y / (hi.y - lo.y)
        dz = ray.direction.z / (hi.z - lo.z)
        length = sqrt(dx * dx + dy * dy + dz * dz)
        ray_direction = (dx / length, dy / length, dz / length)
        middle = [(a + b) / 2 for a, b in zip(ranges[:3], ranges[3:], strict=True)]
        vectors = [middle.copy() for _ in range(4)]
        for i in range(3):
            vectors[i + 1][i] = ranges[i + 3]
        axis_pixels = []
        for vector in vectors:
            pixel = implot3d.plot_to_pixels(*vector)
            axis_pixels.append((pixel.x, pixel.y))

    with TemporaryDirectory(prefix="datelier-faces-") as folder:
        source = args.source or Path(folder) / "data.parquet"
        if args.source is None:
            rng = np.random.default_rng(19)
            pl.DataFrame(
                rng.normal(size=(60, 3)), schema=["x", "y", "z"]
            ).write_parquet(source)
        before = sha256(source.read_bytes()).hexdigest()

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal \
                stage, \
                entered, \
                face_index, \
                baseline_ranges, \
                baseline_rotation, \
                chosen
            active, dashboard = session.loader.active, session.explorer.active
            if active is None or dashboard is None:
                return
            io = imgui.get_io()
            age = evidence.frames - entered
            view = session.exploration.scatter3d
            assert age < 120, (stage, face_index, menu_pixel, item_pixels, view.frames)

            def move(pixel: tuple[float, float]) -> None:
                io.mouse_pos = imgui.ImVec2(*pixel)
                io.want_set_mouse_pos = True

            def advance(next_stage: int) -> None:
                nonlocal stage, entered
                stage, entered = next_stage, evidence.frames
                if args.verbose:
                    print(
                        f"Frame {entered}: stage {stage}, face {face_index}", flush=True
                    )

            if stage == 0:
                session.exploration.tab = "Scatter"
                if args.embedding:
                    session.analysis.controls.features = list(session.plots.numeric[:3])
                    session.analysis.controls.dimensions = 3
                    session.analysis.controls.start(
                        session.analysis.jobs, active.dataset, Algorithm.PCA
                    )
                else:
                    session.plots.three_d = session.plots.custom_scatter = True
                    (
                        session.plots.x_index,
                        session.plots.y_index,
                        session.plots.z_index,
                    ) = (0, 1, 2)
                    session.explorer.request(active.dataset, session.plots.settings())
                advance(1)
            elif stage == 1 and age > 20 and view.frames > 10:
                points = (
                    session.analysis.plots.active
                    if args.embedding
                    else dashboard.scatters[0]
                )
                assert points is not None
                chosen = int(points.row_ids[0])
                session.selection.choose(active.dataset.revision, (chosen,))
                baseline_ranges = ranges
                move(menu_pixel)
                advance(2)
            elif age > 3:
                if stage == 2:
                    item_pixels.clear()
                    io.add_mouse_button_event(0, True)
                    advance(3)
                elif stage == 3:
                    io.add_mouse_button_event(0, False)
                    advance(4)
                elif stage == 4 and faces[face_index] in item_pixels:
                    move(item_pixels[faces[face_index]])
                    advance(5)
                elif stage == 5:
                    io.add_mouse_button_event(0, True)
                    advance(6)
                elif stage == 6:
                    io.add_mouse_button_event(0, False)
                    advance(7)
                elif stage == 7 and age > 10:
                    face = faces[face_index]
                    q = implot3d.Quat.from_el_az(*map(radians, FACE_VIEWS[face]))
                    np.testing.assert_allclose(
                        rotation, (q.x, q.y, q.z, q.w), atol=1e-6
                    )
                    np.testing.assert_allclose(ranges, baseline_ranges)
                    assert unlocked and session.selection.row_ids == {chosen}
                    normal = (
                        2
                        if "XY" in face
                        else 1
                        if "XZ" in face
                        else 0
                        if "YZ" in face
                        else None
                    )
                    lengths = np.linalg.norm(
                        np.array(axis_pixels[1:]) - np.array(axis_pixels[0]), axis=1
                    )
                    if normal is not None:
                        assert lengths[normal] < 1e-4, (face, lengths)
                        assert all(lengths[i] > 5 for i in range(3) if i != normal)
                        direction = {
                            "Top (XY)": (0, 0, -1),
                            "Bottom (XY)": (0, 0, 1),
                            "Front (XZ)": (0, 1, 0),
                            "Back (XZ)": (0, -1, 0),
                            "Left (YZ)": (1, 0, 0),
                            "Right (YZ)": (-1, 0, 0),
                        }[face]
                        np.testing.assert_allclose(ray_direction, direction, atol=1e-6)
                    face_index += 1
                    if face_index < len(faces):
                        move(menu_pixel)
                        advance(2)
                    else:
                        baseline_rotation = rotation
                        move(view.center_pixel)
                        advance(8)
                elif stage == 8:
                    io.add_mouse_button_event(1, True)
                    advance(9)
                elif stage == 9:
                    x, y = view.center_pixel
                    move((x + 30, y + 15))
                    advance(10)
                elif stage == 10:
                    io.add_mouse_button_event(1, False)
                    advance(11)
                elif stage == 11 and age > 10:
                    assert not np.allclose(rotation, baseline_rotation), "locked camera"
                    baseline_rotation = rotation
                    session.exploration.scatter_area.expanded = True
                    advance(12)
                elif stage == 12 and age > 10:
                    np.testing.assert_allclose(rotation, baseline_rotation)
                    np.testing.assert_allclose(ranges, baseline_ranges)
                    assert menu_pixel[0] > 0
                    # Select Top through the same menu inside the expanded window.
                    faces.append("Top (XY)")
                    move(menu_pixel)
                    advance(2)
                elif stage == 13 and age > 10:
                    np.testing.assert_allclose(rotation, baseline_rotation)
                    assert view.selected_points == 1
                    assert sha256(source.read_bytes()).hexdigest() == before
                    hello_imgui.get_runner_params().app_shall_exit = True
                if stage == 8 and session.exploration.scatter_area.expanded:
                    baseline_rotation = rotation
                    session.exploration.scatter_area.expanded = False
                    advance(13)

        with (
            patch.object(imgui, "button", side_effect=record_button),
            patch.object(imgui, "selectable", side_effect=record_item),
            patch.object(Scatter3DView, "_interact", record_camera),
        ):
            evidence = run_gui(source, smoke_frames=2500, on_frame=frame)
        assert stage == 13
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        h, w = pixels.shape[:2]
        args.output.write_bytes(
            f"P6\n{w} {h}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        report = {
            "frames": evidence.frames,
            "face_clicks": faces,
            "projected_planes": True,
            "camera_side_directions": True,
            "free_rotation_after_preset": True,
            "expanded_face_menu": True,
            "ranges_and_selection_preserved": True,
            "embedding": args.embedding,
            "source_sha256": before,
        }
        args.output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
