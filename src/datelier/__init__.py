import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Datelier data inspection workbench")
    parser.add_argument(
        "csv", nargs="?", type=Path, help="open a CSV in the desktop workbench"
    )
    parser.add_argument(
        "--feasibility",
        action="store_true",
        help="open the synthetic docking/plot probe",
    )
    parser.add_argument(
        "--smoke-frames",
        type=int,
        default=0,
        help="exit the GUI after this many frames (smoke verification)",
    )
    args = parser.parse_args()
    if args.smoke_frames < 0:
        parser.error("--smoke-frames requires a nonnegative count")
    if args.csv and args.feasibility:
        parser.error("Choose a CSV or --feasibility")
    if args.feasibility:
        from datelier.feasibility.fixtures import make_table
        from datelier.feasibility.gui import run_gui

        evidence = run_gui(make_table(256), smoke_frames=args.smoke_frames)
        print(f"Rendered {evidence.frames} frames; {evidence.plot_frames} plot frames.")
    else:
        from datelier.gui import run_gui

        evidence = run_gui(args.csv, smoke_frames=args.smoke_frames)
        if args.smoke_frames:
            print(f"Rendered {evidence.frames} frames.")
