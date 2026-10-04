"""Live heatmap navigation and grid/linked-highlight checks."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui
from numpy.typing import NDArray

from datelier.gui import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    stage, entered = 0, 0
    with TemporaryDirectory(prefix="datelier-matrix-") as folder:
        source = Path(folder) / "data.parquet"
        pl.DataFrame({"x": range(30), "y": np.sin(np.arange(30))}).write_parquet(source)

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, entered
            dashboard, active = session.explorer.active, session.loader.active
            if dashboard is None or active is None:
                return
            io = imgui.get_io()
            age = evidence.frames - entered
            relationship = session.exploration.relationships
            if stage == 0:
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
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(source, smoke_frames=1500, on_frame=frame)
        assert stage == 5
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
                }
            )
        )


if __name__ == "__main__":
    main()
