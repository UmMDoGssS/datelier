"""Live heatmap navigation and grid/linked-highlight checks."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import patch

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui
from numpy.typing import NDArray

from datelier.gui import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wide", action="store_true")
    args = parser.parse_args()
    stage, entered = 0, 0
    choices: list[str] = []
    original_combo = imgui.combo

    def record_combo(label: str, index: int, items: list[str]) -> tuple[bool, int]:
        nonlocal choices
        if label == "##Chart type":
            choices = items.copy()
        return original_combo(label, index, items)

    with TemporaryDirectory(prefix="datelier-matrix-") as folder:
        source = Path(folder) / "data.parquet"
        values = {"x": np.arange(30), "y": np.sin(np.arange(30))}
        if args.wide:
            values.update({f"extra{i}": np.cos(np.arange(30) + i) for i in range(10)})
        pl.DataFrame(values).write_parquet(source)

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, entered
            dashboard, active = session.explorer.active, session.loader.active
            if dashboard is None or active is None:
                return
            assert dashboard.relationships is not None
            io = imgui.get_io()
            age = evidence.frames - entered
            relationship = session.exploration.relationships
            if stage == 0:
                if args.wide and len(dashboard.relationships.names) != 2:
                    session.plots.relationship_features = ["x", "y"]
                    session.explorer.request(active.dataset, session.plots.settings())
                    return
                session.exploration.tab = "Correlations"
                stage, entered = 1, evidence.frames
            elif stage == 1 and age > 15:
                io.mouse_pos = imgui.ImVec2(*relationship.pair_pixel)
                io.want_set_mouse_pos = True
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 3, evidence.frames
            elif stage == 3 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 4, evidence.frames
            elif stage == 4 and age > 15:
                assert dashboard.settings.scatter_pair == ("y", "x")
                session.exploration.tab = "Correlations"
                relationship.mode = 1
                session.selection.choose(active.dataset.revision, (0,))
                stage, entered = 5, evidence.frames
            elif stage == 5 and age > 15:
                assert relationship.interactions[(0, 1)].selected_points == 1
                if args.wide:
                    session.plots.relationship_features = list(session.plots.numeric)
                    session.explorer.request(active.dataset, session.plots.settings())
                    stage, entered = 6, evidence.frames
                else:
                    hello_imgui.get_runner_params().app_shall_exit = True
            elif stage == 6 and age > 15:
                assert dashboard.relationships is not None
                assert len(dashboard.relationships.names) == 12
                assert relationship.mode == 0 and choices == ["Heatmap"]
                hello_imgui.get_runner_params().app_shall_exit = True

        with patch.object(imgui, "combo", side_effect=record_combo):
            evidence = run_gui(source, smoke_frames=1500, on_frame=frame)
        assert stage == (6 if args.wide else 5)
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        h, w = pixels.shape[:2]
        Path("/tmp/datelier-relationships.ppm").write_bytes(
            f"P6\n{w} {h}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        print(
            json.dumps(
                {
                    "frames": evidence.frames,
                    "heatmap_navigation": True,
                    "grid_linked_selection": True,
                    "wide_grid_option_hidden": args.wide,
                }
            )
        )


if __name__ == "__main__":
    main()
