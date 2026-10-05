"""Exercise every comparison renderer on a live Linux GUI."""

import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui
from numpy.typing import NDArray

from datelier.gui.app import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    stage, ready = 0, 0
    modes: list[int] = []
    with TemporaryDirectory(prefix="datelier-compare-") as folder:
        source = Path(folder) / "data.parquet"
        pl.DataFrame(
            {"x": np.linspace(-3, 3, 100), "y": np.sin(np.linspace(-3, 3, 100))}
        ).write_parquet(source)

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, ready
            active = session.loader.active
            dashboard = session.explorer.active
            if active is None:
                return
            if stage == 5 and not session.explorer.busy:
                assert (
                    dashboard is None and "failed" in session.explorer.message.lower()
                )
                # Render the recovery controls before requesting corrected axes.
                if evidence.frames > ready + 10:
                    session.explorer.request(active.dataset, session.plots.settings())
                    stage = 6
            if dashboard is None:
                return
            if stage == 0:
                session.plots.compare_columns = ["x", "y"]
                session.exploration.profile.selection.columns = ("x", "y")
                session.explorer.request(active.dataset, session.plots.settings())
                stage = 1
            elif stage == 1 and dashboard.comparison is not None:
                ready, stage = evidence.frames, 2
            elif stage == 2 and evidence.frames > ready + 15:
                modes.append(session.exploration.profile_mode)
                if len(modes) == 5:
                    session.plots.custom_scatter = True
                    session.plots.choose_color("Column")
                    session.plots.color_index = (
                        session.plots.color_columns.index("y") + 1
                    )
                    session.explorer.request(active.dataset, session.plots.settings())
                    session.exploration.tab = "Scatter"
                    stage, ready = 3, evidence.frames
                else:
                    session.exploration.profile_mode += 1
                    ready = evidence.frames

            elif stage == 3 and evidence.frames > ready + 20:
                assert dashboard.scatters[0].colors is not None
                session.selection.choose(active.dataset.revision, (0,))
                stage, ready = 4, evidence.frames
            elif stage == 4 and evidence.frames > ready + 10:
                assert session.exploration.interaction.selected_points == 1
                session.explorer.request(
                    active.dataset,
                    replace(session.plots.settings(), scatter_pair=("x", "x")),
                )
                stage, ready = 5, evidence.frames
            elif stage == 6:
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(source, smoke_frames=10000, on_frame=frame)
        assert modes == list(range(5))
        assert stage == 6
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        h, w = pixels.shape[:2]
        Path("/tmp/datelier-comparison.ppm").write_bytes(
            f"P6\n{w} {h}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        print(
            json.dumps(
                {"frames": evidence.frames, "modes": modes, "error_recovery": True}
            )
        )


if __name__ == "__main__":
    main()
