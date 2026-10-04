"""Live automatic profiles/scatter, edit invalidation, and dashboard gate."""

import argparse
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui
from numpy.typing import NDArray

from datelier.gui import GuiSession, InspectionEvidence, run_gui
from datelier.operations import Sort


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-exploration.ppm")
    )
    parser.add_argument("--settings", action="store_true")
    args = parser.parse_args()
    stage, ready_frame = 0, 0
    with TemporaryDirectory(prefix="datelier-explore-") as directory:
        source = Path(directory) / "data.parquet"
        pl.DataFrame(
            {
                "x": [1, 3, 2],
                "y": [2, 6, 4],
                "category": ["a", "b", "a"],
                "day": [date(2024, 1, i) for i in (1, 2, 3)],
            }
        ).write_parquet(source)
        original = source.read_bytes()

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, ready_frame
            dashboard = session.explorer.active
            active = session.loader.active
            if dashboard is None or active is None:
                return
            assert dashboard.revision == active.dataset.revision
            if stage == 0 and session.exploration.plot_frames > 5:
                assert dashboard.profiles.columns[0].mean == 2
                assert dashboard.profiles.columns[2].distribution.counts == (2, 1)
                session.exploration.profile_index = 2
                stage, ready_frame = 1, evidence.frames
            elif stage == 1 and evidence.frames > ready_frame + 10:
                session.exploration.profile_index = 3
                stage, ready_frame = 2, evidence.frames
            elif stage == 2 and evidence.frames > ready_frame + 10:
                assert dashboard.profiles.columns[3].minimum == "2024-01-01"
                session.exploration.tab = "Correlations"
                stage, ready_frame = 3, evidence.frames
            elif stage == 3 and evidence.frames > ready_frame + 10:
                session.exploration.tab = "Scatter"
                stage = 4
            elif stage == 4 and session.exploration.scatter_frames > 5:
                assert dashboard.scatters[0].row_ids.tolist() == [0, 1, 2]
                session.editor.request(Sort(("x",)))
                stage = 5
            elif stage == 5 and active.first_page.row_ids == (0, 2, 1):
                assert dashboard.scatters[0].row_ids.tolist() == [0, 2, 1]
                stage, ready_frame = 6, evidence.frames
            elif stage == 6 and evidence.frames > ready_frame + 30:
                if args.settings:
                    imgui.set_next_item_open(True, imgui.Cond_.always)
                    stage, ready_frame = 7, evidence.frames
                else:
                    hello_imgui.get_runner_params().app_shall_exit = True
            elif stage == 7 and evidence.frames > ready_frame + 10:
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(source, smoke_frames=1000, on_frame=frame)
        assert stage == (7 if args.settings else 6) and source.read_bytes() == original
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        height, width = pixels.shape[:2]
        args.output.write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        report = {
            "frames": evidence.frames,
            "known_profiles": True,
            "automatic_scatter": True,
            "edit_invalidation": True,
            "source_preserved": True,
        }
        args.output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
