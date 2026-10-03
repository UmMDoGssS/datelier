import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Datelier data inspection workbench")
    parser.add_argument(
        "--feasibility",
        action="store_true",
        help="open the synthetic docking/plot probe",
    )
    parser.add_argument(
        "--smoke-frames",
        type=int,
        default=0,
        help="exit the probe after this many frames",
    )
    args = parser.parse_args()
    if args.smoke_frames < 0 or (args.smoke_frames and not args.feasibility):
        parser.error("--smoke-frames requires --feasibility and a nonnegative count")
    if args.feasibility:
        from datelier.feasibility.fixtures import make_table
        from datelier.feasibility.gui import run_gui

        evidence = run_gui(make_table(256), smoke_frames=args.smoke_frames)
        print(f"Rendered {evidence.frames} frames; {evidence.plot_frames} plot frames.")
    else:
        parser.print_help()
