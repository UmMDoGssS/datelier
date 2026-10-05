"""Measure live new-format loading and bounded previews on the Linux GUI."""

import argparse
import json
import resource
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import cast
from xml.sax.saxutils import escape

import numpy as np
from imgui_bundle import hello_imgui
from numpy.typing import NDArray

from datelier.feasibility.fixtures import make_table
from datelier.gui.app import GuiSession, InspectionEvidence, run_gui
from datelier.io.loading import LoadPhase
from datelier.io.types import ImportFormat


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format", choices=[str(f) for f in ImportFormat], required=True
    )
    parser.add_argument("--rows", type=int, default=1000000)
    parser.add_argument("--numeric-columns", type=int, default=6)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    format = ImportFormat(args.format)
    expected = make_table(args.rows, args.numeric_columns)
    expected_nulls = list(expected.null_count().row(0))
    loading_intervals: list[float] = []
    started = 0.0
    published_ms = 0.0
    ready_frame = 0
    visible_ms = 0.0
    with TemporaryDirectory(prefix="datelier-format-loading-") as directory:
        path = Path(directory) / ("fixture." + format.lower())
        if format in (ImportFormat.CSV, ImportFormat.TSV):
            expected.write_csv(
                path, separator="\t" if format == ImportFormat.TSV else ","
            )
        elif format == ImportFormat.JSON:
            expected.write_json(path)
        elif format == ImportFormat.JSONL:
            expected.write_ndjson(path)
        elif format == ImportFormat.PARQUET:
            expected.write_parquet(path)
        else:
            with path.open("w") as output:
                output.write("<rows>")
                for row in expected.iter_rows():
                    output.write("<row>")
                    for name, value in zip(expected.columns, row, strict=True):
                        text = "" if value is None else escape(str(value))
                        output.write(f"<{name}>{text}</{name}>")
                    output.write("</row>")
                output.write("</rows>")
        before = path.stat()

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal started, published_ms, ready_frame, visible_ms
            if evidence.frames == 30:
                session.controls.path = str(path)
                session.loader.request(path)
                started = perf_counter()
            elif session.loader.status.phase == LoadPhase.LOADING:
                loading_intervals.append(evidence.frame_intervals_ms[-1])
            elif session.loader.status.phase == LoadPhase.FAILED:
                raise RuntimeError(session.loader.status.message)
            active = session.loader.active
            if active and not ready_frame:
                published_ms = (perf_counter() - started) * 1000
                ready_frame = evidence.frames
                assert active.imported.format == format
                assert active.row_count == args.rows
                assert [s.null_count for s in active.schema] == expected_nulls
                session.table.target_row = args.rows - 10
                session.table.jump = True
                if args.numeric_columns > 16:
                    session.table.column_start = 48
            if ready_frame and session.table.last_visible_row >= args.rows - 20:
                if session.table.prepared_visible_rows == session.table.rendered_rows:
                    if not visible_ms:
                        visible_ms = (perf_counter() - started) * 1000
                    page = session.pages.get(
                        session.table.last_visible_row, session.table.column_start
                    )
                    assert page is not None
                    offset = session.table.last_visible_row - page.row_start
                    assert page.row_ids[offset] == session.table.last_visible_row
            if ready_frame and evidence.frames > ready_frame + 60:
                hello_imgui.get_runner_params().app_shall_exit = True
            if started and perf_counter() - started > 90:
                raise TimeoutError("Live import exceeded 90 seconds")

        evidence = run_gui(smoke_frames=10000, on_frame=frame)
        assert visible_ms and evidence.max_rendered_rows < 100
        assert evidence.table_dock_id and evidence.schema_dock_id
        after = path.stat()
        assert (before.st_size, before.st_mtime_ns) == (
            after.st_size,
            after.st_mtime_ns,
        )
        p95 = float(np.percentile(loading_intervals, 95)) if loading_intervals else 0.0
        assert p95 <= 33, f"Loading frame p95 exceeded budget: {p95}"
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        assert peak <= 1024, f"GUI memory exceeded fixture budget: {peak}"
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        height, width = pixels.shape[:2]
        args.output.write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        report = {
            "format": str(format),
            "rows": args.rows,
            "columns": expected.width,
            "background_to_prepared_ms": published_ms,
            "background_to_last_visible_ms": visible_ms,
            "loading_frame_p95_ms": p95,
            "loading_frame_count": len(loading_intervals),
            "peak_rss_mib": peak,
            **asdict(evidence),
        }
        args.output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {
                    key: value
                    for key, value in report.items()
                    if key != "frame_intervals_ms"
                }
            )
        )


if __name__ == "__main__":
    main()
