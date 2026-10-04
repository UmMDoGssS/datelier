"""Render a selected profile using a real source or a deterministic fixture."""

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui
from numpy.typing import NDArray

from datelier.gui import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--column", default="category")
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-profile.ppm")
    )
    args = parser.parse_args()
    with TemporaryDirectory(prefix="datelier-profile-") as folder:
        source = args.source or Path(folder) / "data.parquet"
        if args.source is None:
            pl.DataFrame(
                {
                    "value": [1.0, 2.0, 2.0, 5.0, None],
                    "category": ["female", "male", "male", "female", None],
                    "day": [date(2024, 1, i) for i in (1, 2, 2, 4, 5)],
                }
            ).write_parquet(source)
        original = hashlib.sha256(source.read_bytes()).hexdigest()
        ready = 0
        observed: dict[str, object] = {}

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal ready
            dashboard = session.explorer.active
            if dashboard is None:
                return
            index = [p.name for p in dashboard.profiles.columns].index(args.column)
            session.exploration.profile_index = index
            if not ready:
                ready = evidence.frames
            if evidence.frames > ready + 25:
                profile, bars = dashboard.profiles.columns[index], dashboard.bars[index]
                assert sum(bars.counts) == profile.counted_rows
                observed.update(
                    column=profile.name,
                    rows=dashboard.profiles.row_count,
                    included=profile.counted_rows,
                    missing=profile.null_count,
                    labels=bars.labels,
                    edges=bars.edges.tolist(),
                    temporal_ticks=bars.tick_labels,
                    plots_rendered=session.exploration.plot_frames,
                )
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(source, smoke_frames=600, on_frame=frame)
        assert observed and evidence.frames < 600
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        height, width = pixels.shape[:2]
        args.output.write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        observed["source_preserved"] = (
            original == hashlib.sha256(source.read_bytes()).hexdigest()
        )
        assert observed["source_preserved"]
        args.output.with_suffix(".json").write_text(
            json.dumps(observed, indent=2) + "\n"
        )
        print(json.dumps(observed))


if __name__ == "__main__":
    main()
