"""Run on a Linux display; capture the final framebuffer as portable RGB pixels."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import cast

import numpy as np
from imgui_bundle import hello_imgui
from numpy.typing import NDArray

from datelier.feasibility.fixtures import make_table
from datelier.feasibility.gui import run_gui
from datelier.feasibility.plot_data import DEFAULT_POINT_LIMIT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=256)
    parser.add_argument("--numeric-columns", type=int, default=6)
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--point-limit", type=int, default=DEFAULT_POINT_LIMIT)
    parser.add_argument("--output", type=Path, default=Path("/tmp/datelier-gui.ppm"))
    args = parser.parse_args()
    if args.frames < 20:
        parser.error("Require at least 20 frames for warmup and docking")
    evidence = run_gui(
        make_table(args.rows, args.numeric_columns),
        smoke_frames=args.frames,
        point_limit=args.point_limit,
    )
    if not (
        evidence.frames == args.frames
        and evidence.plot_frames > 0
        and evidence.preview_dock_id
        and evidence.plot_dock_id
        and evidence.preview_dock_id != evidence.plot_dock_id
    ):
        raise RuntimeError(f"Docking/plot smoke gate failed: {evidence}")
    # The dependency annotates this boundary as an unparameterized ndarray.
    pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
    height, width = pixels.shape[:2]
    args.output.write_bytes(
        f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
    )
    report = {
        **asdict(evidence),
        "frame_p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
        "rows": args.rows,
        "numeric_columns": args.numeric_columns,
        "point_limit": args.point_limit,
    }
    args.output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "frame_intervals_ms"}
        )
    )


if __name__ == "__main__":
    main()
