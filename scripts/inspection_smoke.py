"""CSV GUI gates on a Linux display; captures pixels and measured behavior."""

import argparse
import json
import resource
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import perf_counter
from typing import cast

import numpy as np
from imgui_bundle import hello_imgui, imgui
from numpy.typing import NDArray

from datelier.dataset import DatasetRevision
from datelier.feasibility.fixtures import make_table
from datelier.gui import GuiSession, InspectionEvidence, run_gui
from datelier.import_csv import CsvImport, CsvOptions, load_csv
from datelier.loading import DatasetLoader, LoadPhase


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=10000)
    parser.add_argument("--numeric-columns", type=int, default=6)
    parser.add_argument("--frames", type=int, default=180)
    parser.add_argument(
        "--scenario", choices=("preview", "switch-failure"), default="preview"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-inspection.ppm")
    )
    args = parser.parse_args()
    if args.frames < 120 or args.rows < 2:
        parser.error("Require at least 120 frames and 2 rows")
    release, started = Event(), Event()
    observed: dict[str, bool | int | float] = {}
    scroll_started: float | None = None
    wheel_started: float | None = None
    wheel_row = 0
    reload_started: float | None = None
    reload_revision: DatasetRevision | None = None
    reload_published_frame = 0
    with TemporaryDirectory(prefix="datelier-inspection-") as directory:
        root = Path(directory)
        path = root / "fixture.csv"
        table = make_table(args.rows, args.numeric_columns)
        table.write_csv(path)
        del table
        newer = root / "newer.csv"
        newer.write_text("id,label,value\n99,newest,1.5\n12,second,\n")

        def importer(source: Path, options: CsvOptions) -> CsvImport:
            if source == path and args.scenario == "switch-failure":
                started.set()
                if not release.wait(30):
                    raise TimeoutError("Smoke parser was not released")
            return load_csv(source, options)

        loader = DatasetLoader(importer)

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal scroll_started, wheel_started, wheel_row
            nonlocal reload_started, reload_revision, reload_published_frame
            if args.scenario == "preview" and evidence.frames == 20:
                reload_started = perf_counter()
                reload_revision = session.loader.revision
                session.loader.request(path)
            if reload_started is not None:
                if evidence.frame_intervals_ms:
                    observed["reload_max_frame_ms"] = max(
                        float(observed.get("reload_max_frame_ms", 0)),
                        evidence.frame_intervals_ms[-1],
                    )
                if session.loader.revision != reload_revision:
                    if not reload_published_frame:
                        reload_published_frame = evidence.frames
                    elif session.table.prepared_visible_rows:
                        observed["reload_to_visible_ms"] = (
                            perf_counter() - reload_started
                        ) * 1000
                        observed["background_reload_verified"] = True
                        reload_started = None
            if args.scenario == "switch-failure":
                if (
                    started.is_set()
                    and evidence.frames >= 30
                    and not observed.get("switch")
                ):
                    session.loader.request(newer)
                    observed["switch"] = True
                active = session.loader.active
                if active and active.dataset.source.path == newer:
                    observed["newer_won"] = True
                    assert active.dataset.table.rows() == [
                        (99, "newest", 1.5),
                        (12, "second", None),
                    ]
                    if evidence.frames >= 60 and not observed.get("failure_requested"):
                        session.loader.request(root / "missing.csv")
                        observed["failure_requested"] = True
                        release.set()
                if session.loader.status.phase == LoadPhase.FAILED:
                    observed["failure_visible"] = True
                    assert active is not None and active.dataset.source.path == newer
                    if not session.loader.retired_running:
                        observed["stale_ignored"] = True
            elif evidence.frames == 60:
                session.table.target_row = args.rows - 10
                session.table.jump = True
                if args.numeric_columns > 16:
                    session.table.column_start = 48
                scroll_started = perf_counter()
            elif (
                scroll_started is not None
                and session.table.last_visible_row >= args.rows - 20
                and session.table.prepared_visible_rows == session.table.rendered_rows
                and session.table.rendered_rows > 0
            ):
                observed["scroll_to_prepared_ms"] = (
                    perf_counter() - scroll_started
                ) * 1000
                observed["last_visible_row"] = session.table.last_visible_row
                observed["column_start"] = session.table.column_start
                active = session.loader.active
                assert active is not None
                page = session.pages.get(
                    session.table.last_visible_row, session.table.column_start
                )
                assert page is not None
                offset = session.table.last_visible_row - page.row_start
                assert page.row_ids[offset] == session.table.last_visible_row
                observed["row_identity_verified"] = True
                scroll_started = None
            if args.scenario == "preview" and evidence.frames == 100:
                wheel_row = session.table.first_visible_row
                wheel_started = perf_counter()
                imgui.get_io().add_mouse_pos_event(800, 400)
                imgui.get_io().add_mouse_wheel_event(0, 5)
            elif (
                wheel_started is not None
                and session.table.first_visible_row < wheel_row
                and session.table.prepared_visible_rows == session.table.rendered_rows
            ):
                observed["wheel_to_prepared_ms"] = (
                    perf_counter() - wheel_started
                ) * 1000
                observed["wheel_scrolled"] = True
                wheel_started = None
            if evidence.frames == 120:
                imgui.get_io().add_mouse_pos_event(-1000, -1000)

        try:
            evidence = run_gui(
                path, smoke_frames=args.frames, on_frame=frame, dataset_loader=loader
            )
        finally:
            release.set()
        if evidence.frames != args.frames or not evidence.first_preview_ms:
            raise RuntimeError(f"No usable preview: {evidence}")
        if not (evidence.table_dock_id and evidence.schema_dock_id):
            raise RuntimeError("Panels did not dock")
        if evidence.max_rendered_rows >= 100:
            raise RuntimeError("Preview did not stay bounded to visible rows")
        if args.scenario == "switch-failure":
            if not all(
                observed.get(key)
                for key in ("newer_won", "failure_visible", "stale_ignored")
            ):
                raise RuntimeError(f"Switch/failure gate incomplete: {observed}")
            if evidence.loading_frames < 20 or evidence.failed_frames == 0:
                raise RuntimeError("Loading/failure states did not render")
        elif not (
            observed.get("row_identity_verified")
            and observed.get("wheel_scrolled")
            and observed.get("background_reload_verified")
        ):
            raise RuntimeError(f"Scroll gate incomplete: {observed}")
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        height, width = pixels.shape[:2]
        args.output.write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        report = {
            **asdict(evidence),
            "frame_p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            "rows": args.rows,
            "columns": args.numeric_columns + 2,
            "scenario": args.scenario,
            "observed": observed,
        }
        args.output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps({k: v for k, v in report.items() if k != "frame_intervals_ms"})
        )


if __name__ == "__main__":
    main()
