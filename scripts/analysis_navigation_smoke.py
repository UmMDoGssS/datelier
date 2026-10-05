"""Click Analysis inputs before fitting, including an inactive or hidden panel."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl
from imgui_bundle import hello_imgui, imgui

from datelier.analysis_types import Algorithm
from datelier.gui import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hidden", action="store_true")
    parser.add_argument("--cluster-context", action="store_true")
    args = parser.parse_args()
    stage, entered = 0, 0
    with TemporaryDirectory(prefix="datelier-analysis-navigation-") as folder:
        source = Path(folder) / "data.parquet"
        pl.DataFrame({"x": range(30), "y": range(30, 60)}).write_parquet(source)

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, entered
            if session.explorer.active is None:
                return
            io = imgui.get_io()
            age = evidence.frames - entered
            params = hello_imgui.get_runner_params()
            if stage == 0:
                window = next(
                    w
                    for w in params.docking_params.dockable_windows
                    if w.label == "Analysis"
                )
                window.is_visible = not args.hidden
                session.exploration.tab = "Scatter"
                session.analysis.source = Algorithm.PCA
                if args.cluster_context:
                    session.plots.choose_color("DBSCAN")
                stage, entered = 1, evidence.frames
            elif stage == 1 and age > 15:
                io.mouse_pos = imgui.ImVec2(*session.analysis.inputs_pixel)
                io.want_set_mouse_pos = True
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 3, evidence.frames
            elif stage == 3 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 4, evidence.frames
            elif stage == 4 and age > 15:
                assert (
                    session.analysis.selected_algorithm(session.plots) == Algorithm.PCA
                )
                assert not session.analysis.jobs.results
                assert not session.analysis.jobs.busy
                assert any(
                    w.label == "Analysis" and w.is_visible
                    for w in params.docking_params.dockable_windows
                )
                params.app_shall_exit = True

        evidence = run_gui(source, smoke_frames=500, on_frame=frame)
        assert stage == 4
        print(
            json.dumps(
                {
                    "frames": evidence.frames,
                    "hidden": args.hidden,
                    "cluster_context": args.cluster_context,
                    "navigation_without_fit": True,
                    "no_implicit_ml": True,
                }
            )
        )


if __name__ == "__main__":
    main()
