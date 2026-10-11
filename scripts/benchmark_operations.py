"""Fresh-process transform/replay/export and live background-edit performance gates."""

import argparse
import json
import os
import platform
import resource
import subprocess
import sys
from dataclasses import replace
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import cast

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui
from numpy.typing import NDArray

from datelier.application.sessions import EditorController
from datelier.feasibility.fixtures import make_table
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.table import prepare_inspection, prepare_page
from datelier.io.exporting import ExportFormat, export_dataset
from datelier.io.tabular import load_csv
from datelier.pipeline.editing import HistoryAction
from datelier.pipeline.history import Pipeline, replay
from datelier.pipeline.operations import (
    Comparison,
    Filter,
    Operation,
    Sort,
    describe_operation,
)
from datelier.pipeline.transforms import (
    DerivedColumn,
    FillMissing,
    Lookup,
    TargetType,
    Unmatched,
)

CASES = ((10_000, 6), (100_000, 6), (1_000_000, 6), (100_000, 64))


def operations(columns: int) -> tuple[Operation, ...]:
    return (
        Sort(("row_id",), True),
        Filter(
            "row_id", Comparison.GE, 0
        ),  # Replaced with the case-specific threshold.
        FillMissing(f"feature_{columns - 1}", 0),
        Lookup(
            "category",
            (("group_0", "zero"), ("group_1", "one"), ("group_2", "two")),
            TargetType.TEXT,
            Unmatched.ERROR,
        ),
        DerivedColumn("score", 'col("feature_0") * 2 + 1'),
    )


def fixture(path: Path, rows: int, columns: int) -> None:
    make_table(rows, columns).write_csv(path)


def measure(rows: int, columns: int) -> dict[str, object]:
    with TemporaryDirectory(prefix="datelier-operation-benchmark-") as directory:
        root = Path(directory)
        path = root / "source.csv"
        fixture(path, rows, columns)
        original = path.stat()
        imported = load_csv(path)
        pipeline = Pipeline.start(imported.dataset)
        timings: list[dict[str, object]] = []
        recipes = list(operations(columns))
        recipes[1] = Filter("row_id", Comparison.GE, rows // 2)
        for operation in recipes:
            started = perf_counter()
            pipeline = pipeline.apply(operation)
            timings.append(
                {
                    "operation": describe_operation(operation),
                    "ms": (perf_counter() - started) * 1000,
                }
            )
        started = perf_counter()
        repeated = replay(pipeline.source, pipeline.operations)
        replay_ms = (perf_counter() - started) * 1000
        assert repeated.table.equals(pipeline.current.table)
        assert repeated.row_ids.equals(pipeline.current.row_ids)
        del repeated
        started = perf_counter()
        restored = pipeline.undo().redo()
        undo_redo_ms = (perf_counter() - started) * 1000
        assert restored.current.table.equals(pipeline.current.table)
        del restored
        started = perf_counter()
        inspection = prepare_inspection(replace(imported, dataset=pipeline.current))
        summary_ms = (perf_counter() - started) * 1000
        started = perf_counter()
        page = prepare_page(pipeline.current, rows // 2 - 100, max(0, columns - 2))
        page_ms = (perf_counter() - started) * 1000
        assert page.row_ids[-1] == rows // 2
        assert inspection.first_page.row_ids[0] == rows - 1
        assert pipeline.current.row_ids.equals(
            pipeline.current.table["row_id"].cast(pl.UInt64)
        )
        export_times = {}
        for format in ExportFormat:
            output = root / (
                "result.csv" if format == ExportFormat.CSV else "result.parquet"
            )
            started = perf_counter()
            export_dataset(pipeline.current, output, format)
            export_times[format.value] = (perf_counter() - started) * 1000
            table = (
                pl.read_csv(output)
                if format == ExportFormat.CSV
                else pl.read_parquet(output)
            )
            assert table.equals(pipeline.current.table)
            del table
        after = path.stat()
        assert (after.st_size, after.st_mtime_ns) == (
            original.st_size,
            original.st_mtime_ns,
        )
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        assert summary_ms <= 250 and page_ms <= 50 and peak <= 1024
        return {
            "rows": rows,
            "columns": columns + 2,
            "source_bytes": original.st_size,
            "operations": timings,
            "replay_ms": replay_ms,
            "undo_redo_ms": undo_redo_ms,
            "summary_ms": summary_ms,
            "last_page_ms": page_ms,
            "export_ms": export_times,
            "peak_rss_mib": peak,
        }


def gui_measure(rows: int, columns: int, output: Path) -> None:
    actions: list[Operation | HistoryAction] = list(operations(columns))
    actions[1] = Filter("row_id", Comparison.GE, rows // 2)
    actions.extend((HistoryAction.UNDO, HistoryAction.REDO))
    index, pending, completed = 0, False, 0
    started = 0.0
    times: list[float] = []
    max_rendered_rows = 0
    with TemporaryDirectory(prefix="datelier-operation-gui-") as directory:
        path = Path(directory) / "source.csv"
        fixture(path, rows, columns)
        original = path.stat()

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal index, pending, completed, started, max_rendered_rows
            session = editor.current
            visible = [
                int(key.path[-3])
                for key in probe.targets
                if key.path[-2:] == ("source", "select")
            ]
            max_rendered_rows = max(max_rendered_rows, len(visible))
            if evidence.frames == 1:
                editor.navigation.context_tab = "Transform"
            active = session.loader.active
            if active is None or session.editor.busy or evidence.frames < 30:
                return
            if pending:
                times.append((perf_counter() - started) * 1000)
                assert active.first_page.row_ids[0] == rows - 1
                assert session.pages.get(0) == active.first_page
                pending = False
                index += 1
            if index < len(actions):
                started = perf_counter()
                session.editor.request(actions[index])
                pending = True
            elif not completed:
                session.table.target_row = active.row_count - 8
                session.table.jump = True
                if columns > 16:
                    session.table.column_start = 48
                completed = evidence.frames
            elif evidence.frames > completed + 60:
                assert visible
                last_position = max(visible)
                assert last_position >= rows // 2 - 8
                page = session.pages.get(last_position, session.table.column_start)
                assert page is not None
                offset = last_position - page.row_start
                assert page.row_ids[offset] == rows - 1 - last_position
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(path, smoke_frames=6000, on_probe_frame=frame)
        assert index == len(actions) and completed
        after = path.stat()
        assert (after.st_size, after.st_mtime_ns) == (
            original.st_size,
            original.st_mtime_ns,
        )
        p95 = float(np.percentile(evidence.frame_intervals_ms, 95))
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        assert p95 <= 33 and peak <= 1024 and max_rendered_rows < 100
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        height, width = pixels.shape[:2]
        output.write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        report = {
            "rows": rows,
            "columns": columns + 2,
            "frames": evidence.frames,
            "frame_p95_ms": p95,
            "peak_rss_mib": peak,
            "edit_to_prepared_ms": times,
            "source_preserved": True,
            "last_page_identity": True,
            "max_rendered_rows": max_rendered_rows,
        }
        output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=int, nargs=2)
    parser.add_argument("--gui", type=int, nargs=2)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-operations-benchmark.json")
    )
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(measure(*args.worker)))
        return
    if args.gui:
        gui_measure(args.gui[0], args.gui[1], args.output)
        return
    measurements = []
    for rows, columns in CASES:
        result = subprocess.run(
            [sys.executable, __file__, "--worker", str(rows), str(columns)],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        measurements.append(json.loads(result.stdout))
        print(f"Passed {rows:,} × {columns + 2}", flush=True)
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu": next(
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        ),
        "logical_cpus": os.cpu_count(),
        "ram_bytes": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
        "polars_threads": pl.thread_pool_size(),
        "versions": {
            name: version(name) for name in ("polars", "imgui-bundle", "numpy")
        },
        "fixture_types": (
            "Int64 row_id, Float64 numeric features, String category; "
            "null every 17 rows in last feature"
        ),
        "measurements": measurements,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
