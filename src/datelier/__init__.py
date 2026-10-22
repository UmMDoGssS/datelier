"""Personal Linux desktop workbench for in-memory data inspection.

The completed tabular and editor/multimodal baseline supports independent source
tabs, reversible Polars operations, explicit analyses, referenced workspaces,
and structured/text/image/audio inspection. Larger-than-memory tables, third-party
plugins, arbitrary Python mappings, and extra platforms need concrete future
requirements. Lazy media stores do not imply an out-of-core table engine.

From a checkout with Python 3.14+ and uv::

    uv sync --locked --no-dev
    uv run --no-dev datelier /path/to/data.csv
    uv run --no-dev datelier --workspace /path/to/session.datelier

Omit the path to open Welcome. The verified renderer is Linux Mesa software
OpenGL; LIBGL_ALWAYS_SOFTWARE=1 selects it. Tables must fit in memory; one million
rows is a benchmark direction, not a capacity guarantee. Optional CPU checkpoints
need --extra checkpoints on both sync and run. Audio playback requires a system
PortAudio runtime; codecs depend on the host's libsndfile build.

Subsystem package/API docstrings own current behavior and constraints. The scripts
package documents verification commands. Completed reports, screenshots, and
the original delivery roadmap remain recoverable at Git snapshot b1b332c; their
commands describe historical checkouts. Titanic human usability and actual audio
listening remain open as described in gui and inspection.audio.playback.
"""

import argparse
from importlib.metadata import version
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Datelier data inspection workbench")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {version('datelier')}"
    )
    parser.add_argument(
        "dataset", nargs="?", type=Path, help="open a dataset in the desktop workbench"
    )
    parser.add_argument("--workspace", type=Path, help="restore a referenced workspace")
    parser.add_argument(
        "--smoke-frames",
        type=int,
        default=0,
        help="exit the GUI after this many frames (smoke verification)",
    )
    args = parser.parse_args()
    if args.smoke_frames < 0:
        parser.error("--smoke-frames requires a nonnegative count")
    if args.dataset is not None and args.workspace is not None:
        parser.error("Choose a dataset or --workspace")
    from datelier.gui.app import run_gui

    evidence = run_gui(
        args.dataset,
        smoke_frames=args.smoke_frames,
        initial_workspace=args.workspace,
    )
    if args.smoke_frames:
        print(f"Rendered {evidence.frames} frames.")
