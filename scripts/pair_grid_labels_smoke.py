"""Native dense-grid axis names, zoom retention and linked-selection checks."""

import argparse
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import patch

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui, implot
from numpy.typing import NDArray

from datelier.gui import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--features", type=int, choices=[5, 8], default=5)
    parser.add_argument("--long-names", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("/tmp/datelier-grid.ppm"))
    args = parser.parse_args()
    stage, entered = 0, 0
    current_cell: tuple[int, int] | None = None
    labels: dict[tuple[int, int], tuple[str, str]] = {}
    bounds: tuple[float, ...] = ()
    original_bounds: tuple[float, ...] = ()
    zoomed_bounds: tuple[float, ...] = ()
    scroll_max = (0.0, 0.0)
    original_begin, original_end = implot.begin_plot, implot.end_plot

    def begin_plot(
        label: str,
        size: imgui.ImVec2 | tuple[float, float] = (-1, 0),
        flags: int = 0,
    ) -> bool:
        nonlocal current_cell
        current_cell = None
        suffix = label.split("##")[-1].split("-")
        if len(suffix) == 2 and all(part.isdecimal() for part in suffix):
            current_cell = (int(suffix[0]), int(suffix[1]))
        return original_begin(label, size, flags)

    def end_plot() -> None:
        nonlocal bounds, scroll_max
        if current_cell is not None:
            scroll_max = (imgui.get_scroll_max_x(), imgui.get_scroll_max_y())
            plot = implot.internal.get_current_plot()
            labels[current_cell] = (
                plot.get_axis_label(plot.x_axis(0))
                if plot.x_axis(0).has_label()
                else "",
                plot.get_axis_label(plot.y_axis(0))
                if plot.y_axis(0).has_label()
                else "",
            )
            if current_cell == (0, 1):
                limits = implot.get_plot_limits()
                bounds = (limits.x.min, limits.x.max, limits.y.min, limits.y.max)
        original_end()

    with TemporaryDirectory(prefix="datelier-grid-") as folder:
        source = args.source or Path(folder) / "data.parquet"
        if args.source is None:
            rng = np.random.default_rng(29)
            names = [
                f"passenger_measurement_{i}" if args.long_names else f"feature_{i}"
                for i in range(args.features)
            ]
            pl.DataFrame(
                rng.normal(size=(60, args.features)), schema=names
            ).write_parquet(source)
        before = sha256(source.read_bytes()).hexdigest()

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, entered, original_bounds, zoomed_bounds
            active, dashboard = session.loader.active, session.explorer.active
            if active is None or dashboard is None:
                return
            view = session.exploration.relationships
            age = evidence.frames - entered
            assert age < 200, (stage, labels)
            io = imgui.get_io()
            if stage == 0:
                names = (
                    ["age", "fare", "pclass", "sibsp", "parch"]
                    if args.source and args.features == 5
                    else list(session.plots.numeric[: args.features])
                )
                assert len(names) == args.features
                session.plots.relationship_features = names
                session.explorer.request(active.dataset, session.plots.settings())
                session.exploration.tab = "Correlations"
                view.mode = 1
                stage, entered = 1, evidence.frames
            elif stage == 1 and age > 20:
                data = dashboard.relationships
                assert data is not None and len(data.names) == args.features
                expected = {
                    (i, j): (x if i == 0 else "", y if j == 0 else "")
                    for i, y in enumerate(data.names)
                    for j, x in enumerate(data.names)
                }
                assert labels == expected, (labels, expected)
                points = data.cells[0][1]
                assert points is not None
                session.selection.choose(
                    active.dataset.revision, (int(points.row_ids[0]),)
                )
                original_bounds = bounds
                io.mouse_pos = imgui.ImVec2(*view.interactions[(0, 1)].center_pixel)
                io.want_set_mouse_pos = True
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 3:
                io.add_mouse_wheel_event(0, 1)
                stage, entered = 3, evidence.frames
            elif stage == 3 and age > 10:
                assert not np.allclose(bounds, original_bounds), "grid wheel zoom"
                assert view.interactions[(0, 1)].selected_points == 1
                zoomed_bounds = bounds
                view.area.expanded = True
                stage, entered = 4, evidence.frames
            elif stage == 4 and age > 10:
                np.testing.assert_allclose(bounds, zoomed_bounds)
                view.area.expanded = False
                stage, entered = 5, evidence.frames
            elif stage == 5 and age > 10:
                np.testing.assert_allclose(bounds, zoomed_bounds)
                assert view.interactions[(0, 1)].selected_points == 1
                assert sha256(source.read_bytes()).hexdigest() == before
                view.area.expanded = True
                io.mouse_pos = imgui.ImVec2(10, 10)
                stage, entered = 6, evidence.frames
            elif stage == 6 and age > 10:
                if args.long_names:
                    assert all(value > 0 for value in scroll_max), scroll_max
                hello_imgui.get_runner_params().app_shall_exit = True

        with (
            patch.object(implot, "begin_plot", side_effect=begin_plot),
            patch.object(implot, "end_plot", side_effect=end_plot),
        ):
            evidence = run_gui(source, smoke_frames=1000, on_frame=frame)
        assert stage == 6
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        h, w = pixels.shape[:2]
        args.output.write_bytes(
            f"P6\n{w} {h}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        report = {
            "frames": evidence.frames,
            "features": args.features,
            "long_names": args.long_names,
            "native_axis_names": {
                f"{i},{j}": value for (i, j), value in labels.items()
            },
            "wheel_zoom": True,
            "expanded_ranges_preserved": True,
            "linked_selection": True,
            "canvas_scroll_max": scroll_max,
            "source_sha256": before,
        }
        args.output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
