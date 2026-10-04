"""Exercise every comparison renderer on a live Linux GUI."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui
from numpy.typing import NDArray

from datelier.gui import GuiSession, InspectionEvidence, run_gui


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
            if active is None or dashboard is None:
                return
            if stage == 0:
                session.plots.compare_columns = ["x", "y"]
                session.explorer.request(active.dataset, session.plots.settings())
                stage = 1
            elif stage == 1 and dashboard.comparison is not None:
                ready, stage = evidence.frames, 2
            elif stage == 2 and evidence.frames > ready + 15:
                modes.append(session.exploration.comparison_mode)
                if len(modes) == 5:
                    hello_imgui.get_runner_params().app_shall_exit = True
                else:
                    session.exploration.comparison_mode += 1
                    ready = evidence.frames

        evidence = run_gui(source, smoke_frames=10000, on_frame=frame)
        assert modes == list(range(5))
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        h, w = pixels.shape[:2]
        Path("/tmp/datelier-comparison.ppm").write_bytes(
            f"P6\n{w} {h}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        print(json.dumps({"frames": evidence.frames, "modes": modes}))


if __name__ == "__main__":
    main()
