"""Inspect every method on Titanic, including exclusive Colors and linked 3D views."""

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import cast
from unittest.mock import patch

import numpy as np
from imgui_bundle import hello_imgui, imgui
from numpy.typing import NDArray

from datelier.analysis_types import Algorithm, ClusteringResult
from datelier.gui import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("/home/ummdogsss/Downloads/titanic_train.csv"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-unsupervised-titanic.ppm")
    )
    args = parser.parse_args()
    before = sha256(args.source.read_bytes()).hexdigest()
    algorithms = list(Algorithm)
    index, stage, entered = 0, 0, 0
    checks: list[dict[str, object]] = []
    labels: set[str] = set()
    choices_seen: dict[str, list[str]] = {}
    original_combo = imgui.combo

    def record_combo(label: str, selected: int, choices: list[str]) -> tuple[bool, int]:
        if imgui.internal.get_current_window().name == "Explore":
            labels.add(label)
            choices_seen[label] = choices
        return original_combo(label, selected, choices)

    def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
        nonlocal index, stage, entered
        active, dashboard = session.loader.active, session.explorer.active
        if active is None or dashboard is None:
            labels.clear()
            return
        age = evidence.frames - entered
        analysis, plots = session.analysis, session.plots
        algorithm = algorithms[index]
        if stage == 0:
            analysis.source = None
            analysis.controls.features = ["age", "fare", "sibsp", "parch", "pclass"]
            analysis.controls.dimensions = 3
            plots.custom_scatter = plots.three_d = True
            plots.x_index, plots.y_index, plots.z_index = (
                plots.numeric.index(n) for n in ("age", "fare", "pclass")
            )
            plots.choose_color("Uniform")
            session.exploration.tab = "Scatter"
            stage, entered = 1, evidence.frames
        elif stage == 1 and age > 10:
            assert "##Color column" not in labels
            assert choices_seen["##Colors"] == [
                "Uniform",
                "Column",
                *(a.value for a in algorithms if a.is_clustering),
            ]
            assert not analysis.jobs.busy and not analysis.jobs.results
            plots.choose_color("Column")
            plots.color_index = plots.color_columns.index("sex") + 1
            stage, entered = 2, evidence.frames
        elif stage == 2 and age > 10:
            assert "##Color column" in labels
            assert plots.color_column == "sex"
            assert not analysis.jobs.busy and not analysis.jobs.results
            stage, entered = 3, evidence.frames
        elif stage == 3:
            if algorithm.is_clustering:
                analysis.source = None
                plots.choose_color(algorithm.value)
            else:
                plots.choose_color(
                    "DBSCAN" if Algorithm.DBSCAN in analysis.jobs.results else "Column"
                )
                analysis.source = algorithm
            stage, entered = 4, evidence.frames
        elif stage == 4 and age > 10:
            assert not analysis.jobs.busy
            if plots.cluster_color:
                assert "##Color column" not in labels
            io = imgui.get_io()
            io.mouse_pos = imgui.ImVec2(*analysis.run_pixel)
            io.want_set_mouse_pos = True
            io.add_mouse_button_event(0, True)
            stage, entered = 5, evidence.frames
        elif stage == 5 and age > 2:
            imgui.get_io().add_mouse_button_event(0, False)
            stage, entered = 6, evidence.frames
        elif stage == 6 and age > 15:
            if analysis.jobs.message.startswith("Analysis failed"):
                raise AssertionError(f"{algorithm}: {analysis.jobs.message}")
            result = analysis.jobs.results.get(algorithm)
            if result is None:
                return
            points = (
                dashboard.scatters[0]
                if isinstance(result, ClusteringResult)
                else analysis.plots.active
            )
            if points is None:
                return
            if isinstance(result, ClusteringResult):
                if points.colors is None or points.colors.name != algorithm.value:
                    return
            else:
                if not points.x_name.startswith(algorithm.value):
                    return
                if plots.cluster_color and (
                    points.colors is None or points.colors.name != plots.color_source
                ):
                    return
            selected = int(points.row_ids[0])
            session.selection.choose(active.dataset.revision, (selected,))
            summary = result.provenance.input
            checks.append(
                {
                    "method": algorithm.value,
                    "fit_rows": summary.sampled_rows,
                    "excluded": summary.excluded_rows,
                    "runtime_seconds": result.provenance.runtime_seconds,
                }
            )
            stage, entered = 7, evidence.frames
        elif stage == 7 and age > 10:
            assert session.exploration.scatter3d.selected_points == 1
            assert sha256(args.source.read_bytes()).hexdigest() == before
            if index + 1 < len(algorithms):
                index += 1
                stage, entered = 3, evidence.frames
            else:
                # Final view combines the fitted LLE coordinates and DBSCAN colors.
                session.exploration.scatter3d_area.expanded = True
                stage, entered = 8, evidence.frames
        elif stage == 8 and age > 20:
            hello_imgui.get_runner_params().app_shall_exit = True
        labels.clear()

    with patch.object(imgui, "combo", record_combo):
        evidence = run_gui(args.source, smoke_frames=30000, on_frame=frame)
    assert stage == 8 and len(checks) == len(algorithms)
    pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
    height, width = pixels.shape[:2]
    args.output.write_bytes(
        f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
    )
    record = {
        "frames": evidence.frames,
        "methods": checks,
        "conditional_column_picker": True,
        "all_sources_available_before_fit": True,
        "explicit_run_clicks": True,
        "linked_3d": True,
        "dbscan_embedding_colors": True,
        "source_sha256": before,
    }
    args.output.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
