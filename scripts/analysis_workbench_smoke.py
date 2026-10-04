"""Explicit analysis command to linked embedding on the live workbench."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui
from numpy.typing import NDArray

from datelier.analysis_types import Algorithm
from datelier.gui import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    stage, entered = 0, 0
    with TemporaryDirectory(prefix="datelier-analysis-") as folder:
        source = Path(folder) / "data.parquet"
        rng = np.random.default_rng(42)
        values = rng.normal(size=(120, 3)) + np.repeat(np.arange(3), 40)[:, None] * 6
        pl.DataFrame(values, schema=["x", "y", "z"]).write_parquet(source)
        original = source.read_bytes()

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, entered
            active, dashboard = session.loader.active, session.explorer.active
            if active is None or dashboard is None:
                return
            analysis = session.analysis
            age = evidence.frames - entered
            if stage == 0:
                assert not analysis.jobs.busy and not analysis.jobs.results
                analysis.controls.features = ["x", "y", "z"]
                session.exploration.tab = "Scatter"
                analysis.controls.start(analysis.jobs, active.dataset, Algorithm.PCA)
                stage, entered = 1, evidence.frames
            elif stage == 1 and analysis.plots.active is not None:
                assert analysis.source == Algorithm.PCA
                assert analysis.jobs.results[
                    Algorithm.PCA
                ].provenance.request.features == ("x", "y", "z")
                session.selection.choose(active.dataset.revision, (0,))
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 20:
                assert session.exploration.interaction.selected_points == 1
                assert source.read_bytes() == original
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(source, smoke_frames=10000, on_frame=frame)
        assert stage == 2
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        h, w = pixels.shape[:2]
        Path("/tmp/datelier-analysis-workbench.ppm").write_bytes(
            f"P6\n{w} {h}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        print(
            json.dumps(
                {
                    "frames": evidence.frames,
                    "explicit_PCA": True,
                    "linked_embedding": True,
                    "source_preserved": True,
                }
            )
        )


if __name__ == "__main__":
    main()
