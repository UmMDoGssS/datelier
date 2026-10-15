import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Datelier data inspection workbench")
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
