"""Exercise unfitted sources, parameter forms, explicit fit, colors and selection."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui
from numpy.typing import NDArray

from datelier.analysis.types import Algorithm, ClusteringResult
from datelier.gui.analysis.form import show_parameters
from datelier.gui.app import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--method", choices=[a.value for a in Algorithm], default="DBSCAN"
    )
    args = parser.parse_args()
    algorithm = Algorithm(args.method)
    stage, entered = 0, 0
    with TemporaryDirectory(prefix="datelier-unsupervised-") as folder:
        path = Path(folder) / "data.parquet"
        rng = np.random.default_rng(4)
        values = np.r_[
            rng.normal(-3, 0.12, (60, 3)), rng.normal(3, 0.12, (60, 3)), [[0, 9, 0]]
        ]
        pl.DataFrame(values, schema=["x", "y", "z"]).with_columns(
            pl.lit("group").alias("category")
        ).write_parquet(path)
        original = path.read_bytes()

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, entered
            active, dashboard = session.loader.active, session.explorer.active
            if active is None or dashboard is None:
                return
            analysis, plots = session.analysis, session.plots
            age = evidence.frames - entered
            params = hello_imgui.get_runner_params()
            if stage == 0:
                session.exploration.tab = "Scatter"
                analysis.controls.features = ["x", "y", "z"]
                analysis.controls.dimensions = 3
                plots.custom_scatter = plots.three_d = True
                plots.choose_color("Column")
                plots.color_index = plots.color_columns.index("category") + 1
                stage, entered = 1, evidence.frames
            elif stage == 1 and age > 10:
                assert not analysis.jobs.busy and not analysis.jobs.results
                plots.choose_color(
                    algorithm.value if algorithm.is_clustering else "Uniform"
                )
                if not algorithm.is_clustering:
                    analysis.source = algorithm
                stage, entered = 2, evidence.frames
            elif stage == 2:
                # Render every parameter widget before fitting.
                imgui.begin("Parameter smoke")
                show_parameters(analysis.controls, algorithm)
                imgui.end()
                if age > 10:
                    assert not analysis.jobs.busy and not analysis.jobs.results
                    pos = analysis.run_pixel
                    assert min(pos) > 0
                    io = imgui.get_io()
                    io.mouse_pos = imgui.ImVec2(*pos)
                    io.want_set_mouse_pos = True
                    io.add_mouse_button_event(0, True)
                    stage, entered = 3, evidence.frames
            elif stage == 3 and age > 2:
                imgui.get_io().add_mouse_button_event(0, False)
                stage, entered = 4, evidence.frames
            elif stage == 4 and age > 15:
                if analysis.jobs.message.startswith("Analysis failed"):
                    raise AssertionError(analysis.jobs.message)
                result = analysis.jobs.results.get(algorithm)
                if result is None:
                    return
                points = (
                    dashboard.scatters[0]
                    if algorithm.is_clustering
                    else analysis.plots.active
                )
                if points is None:
                    return
                if isinstance(result, ClusteringResult):
                    if points.colors is None or points.colors.name != algorithm.value:
                        return
                    assert points.colors.name == algorithm.value
                selected = int(points.row_ids[0])
                session.selection.choose(active.dataset.revision, (selected,))
                stage, entered = 5, evidence.frames
            elif stage == 5 and age > 20:
                assert session.exploration.scatter3d.selected_points == 1
                assert path.read_bytes() == original
                params.app_shall_exit = True

        evidence = run_gui(path, smoke_frames=10000, on_frame=frame)
        assert stage == 5
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        height, width = pixels.shape[:2]
        Path("/tmp/datelier-unsupervised.ppm").write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        print(
            json.dumps(
                {
                    "method": algorithm.value,
                    "frames": evidence.frames,
                    "explicit_click": True,
                    "no_implicit_fit": True,
                    "parameters_rendered": True,
                    "linked_3d": True,
                    "source_preserved": True,
                }
            )
        )


if __name__ == "__main__":
    main()
