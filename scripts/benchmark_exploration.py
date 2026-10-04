"""Fresh-process exploration and live large/wide interaction acceptance gates."""

import argparse
import json
import os
import platform
import resource
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import cast

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui
from numpy.typing import NDArray

from datelier.distributions import DistributionSettings, prepare_comparison
from datelier.exploration import PlotSettings, prepare_dashboard
from datelier.feasibility.fixtures import make_table
from datelier.gui import GuiSession, InspectionEvidence, run_gui
from datelier.import_csv import load_csv
from datelier.inspection import prepare_inspection, prepare_page
from datelier.operations import Comparison, Filter, Sort
from datelier.pipeline import Pipeline
from datelier.profiling import prepare_profiles
from datelier.selection import LinkedSelection

CASES = ((10_000, 6), (100_000, 6), (1_000_000, 6), (100_000, 64))
# Declared before measurement; existing frame/page/memory budgets are retained.
DEFAULT_PREPARE_MS = 2_000
EXPANDED_PREPARE_MS = 4_000


def measure(rows: int, columns: int) -> dict[str, object]:
    with TemporaryDirectory(prefix="datelier-explore-benchmark-") as directory:
        source = Path(directory) / "source.csv"
        make_table(rows, columns).write_csv(source)
        original = source.stat()
        imported = load_csv(source)
        started = perf_counter()
        prepare_inspection(imported)
        summary_ms = (perf_counter() - started) * 1000
        started = perf_counter()
        prepare_page(imported.dataset, rows - 100)
        page_ms = (perf_counter() - started) * 1000
        started = perf_counter()
        profiles = prepare_profiles(imported.dataset)
        profile_ms = (perf_counter() - started) * 1000
        assert sum(profiles.columns[0].distribution.counts) == rows
        started = perf_counter()
        dashboard = prepare_dashboard(imported.dataset)
        default_ms = (perf_counter() - started) * 1000
        compare_names = tuple(f"feature_{i}" for i in range(min(columns, 8)))
        start_comparison = perf_counter()
        comparison = prepare_comparison(
            imported.dataset,
            DistributionSettings(compare_names, standardize=True),
            bins=100,
        )
        comparison_ms = (perf_counter() - start_comparison) * 1000
        assert all(len(c.ecdf_x) <= 2_000 for c in comparison.series)
        pipeline = (
            Pipeline.start(imported.dataset)
            .apply(Sort(("row_id",), descending=True))
            .apply(Filter("row_id", Comparison.GE, rows // 2))
        )
        settings = PlotSettings(
            profile_columns=128,
            bins=100,
            top_counts=100,
            correlation_columns=16,
            point_limit=10_000,
            scatter_pair=("row_id", f"feature_{columns - 1}"),
        )
        started = perf_counter()
        expanded = prepare_dashboard(pipeline.current, settings)
        expanded_ms = (perf_counter() - started) * 1000
        assert len(dashboard.correlations) <= 28 and len(expanded.correlations) <= 120
        points = expanded.scatters[0]
        expected = pipeline.current.table.get_column("row_id").gather(points.positions)
        assert expected.to_list() == points.row_ids.tolist()
        selected = LinkedSelection()
        selected.bind(pipeline.current.revision)
        interactions = []
        for _index in range(50):
            start = perf_counter()
            middle = len(points.x) // 2
            assert (
                selected.nearest(
                    points, float(points.x[middle]), float(points.y[middle]), 10, 10
                )
                is not None
            )
            selected.rectangle(
                points,
                float(points.x.min()),
                float(points.y.min()),
                float(points.x.max()),
                float(points.y.max()),
            )
            assert len(selected.row_ids) == len(points.x)
            selected.overlay(points)
            interactions.append((perf_counter() - start) * 1000)
        p95 = float(np.percentile(interactions, 95))
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        assert comparison_ms <= EXPANDED_PREPARE_MS
        after = source.stat()
        assert (original.st_size, original.st_mtime_ns) == (
            after.st_size,
            after.st_mtime_ns,
        )
        assert (
            summary_ms <= 250
            and page_ms <= 50
            and default_ms <= DEFAULT_PREPARE_MS
            and expanded_ms <= EXPANDED_PREPARE_MS
        )
        assert p95 <= 33 and peak <= 1024, (p95, peak)
        return {
            "rows": rows,
            "columns": columns + 2,
            "source_bytes": original.st_size,
            "summary_ms": summary_ms,
            "page_ms": page_ms,
            "profiles_ms": profile_ms,
            "default_prepare_ms": default_ms,
            "comparison_prepare_ms": comparison_ms,
            "expanded_prepare_ms": expanded_ms,
            "interaction_p95_ms": p95,
            "interaction_repetitions": 50,
            "peak_rss_mib": peak,
            "expanded_points": len(points.x),
            "expanded_pairs": len(expanded.correlations),
            "row_identity": True,
        }


def gui_measure(
    rows: int,
    columns: int,
    output: Path,
    three_d: bool = False,
    view: str = "scatter",
) -> None:
    stage, ready_frame = 0, 0
    prepare_started, default_ms, expanded_ms = 0.0, 0.0, 0.0
    with TemporaryDirectory(prefix="datelier-explore-gui-") as directory:
        source = Path(directory) / "source.csv"
        make_table(rows, columns).write_csv(source)
        original = source.stat()

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, ready_frame, prepare_started, default_ms, expanded_ms
            active = session.loader.active
            dashboard = session.explorer.active
            if active is None:
                return
            if stage == 0:
                prepare_started = perf_counter()
                stage = 1
            if dashboard is None or dashboard.revision != active.dataset.revision:
                return
            if stage == 1:
                default_ms = (perf_counter() - prepare_started) * 1000
                session.plots.profile_columns = 128
                session.plots.correlation_columns = 16
                session.plots.point_limit = 10_000
                session.plots.three_d = three_d
                session.plots.z_index = 1
                session.plots.custom_scatter = True
                session.plots.x_index, session.plots.y_index = 0, columns
                if view == "grid":
                    session.plots.relationship_features = list(
                        session.plots.numeric[:8]
                    )
                elif view == "comparison":
                    session.plots.compare_columns = list(session.plots.numeric[:8])
                    session.plots.standardize = True
                session.explorer.request(active.dataset, session.plots.settings())
                prepare_started = perf_counter()
                stage = 2
            elif stage == 2:
                expanded_ms = (perf_counter() - prepare_started) * 1000
                assert len(dashboard.scatters[0].x) == 10_000
                session.editor.request(Sort(("row_id",), descending=True))
                stage = 3
            elif stage == 3 and active.first_page.row_ids[0] == rows - 1:
                session.editor.request(Filter("row_id", Comparison.GE, rows // 2))
                stage = 4
            elif stage == 4 and active.row_count == rows // 2:
                points = dashboard.scatters[0]
                assert (
                    points.row_ids.tolist()
                    == active.dataset.table.get_column("row_id")
                    .gather(points.positions)
                    .to_list()
                )
                session.selection.choose(
                    active.dataset.revision, points.row_ids.tolist()
                )
                session.table.target_row, session.table.jump = (
                    int(points.positions[-1]) + 1,
                    True,
                )
                if columns > 16:
                    session.table.column_start = 48
                session.exploration.tab = {
                    "scatter": "Scatter",
                    "grid": "Correlations",
                    "comparison": "Profiles",
                }[view]
                session.exploration.relationships.mode = 1
                session.exploration.comparison_mode = 1
                stage, ready_frame = 5, evidence.frames
            elif stage == 5 and evidence.frames > ready_frame + 90:
                selected_points = (
                    session.exploration.scatter3d.selected_points
                    if three_d
                    else session.exploration.interaction.selected_points
                )
                if view == "scatter":
                    assert selected_points == 10_000
                elif view == "grid":
                    interactions = session.exploration.relationships.interactions
                    assert any(
                        interaction.selected_points > 0
                        for interaction in interactions.values()
                    )
                else:
                    assert dashboard.comparison is not None
                    assert len(dashboard.comparison.series) == min(8, columns + 1)
                assert session.table.selected_visible_rows > 0
                assert (
                    session.table.prepared_visible_rows
                    == session.table.rendered_rows
                    > 0
                )
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(source, smoke_frames=6000, on_frame=frame)
        assert stage == 5 and evidence.first_preview_ms is not None
        p95 = float(np.percentile(evidence.frame_intervals_ms, 95))
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        assert p95 <= 33 and peak <= 1024, (p95, peak)
        assert default_ms <= DEFAULT_PREPARE_MS and expanded_ms <= EXPANDED_PREPARE_MS
        after = source.stat()
        assert (original.st_size, original.st_mtime_ns) == (
            after.st_size,
            after.st_mtime_ns,
        )
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        if three_d:
            orange = (
                (pixels[:, :, 0] > 220)
                & (pixels[:, :, 1] > 140)
                & (pixels[:, :, 1] < 210)
                & (pixels[:, :, 2] < 100)
            )
            assert int(orange.sum()) > 100, "Selected 3D markers must visibly render"
        height, width = pixels.shape[:2]
        output.write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        report = {
            "rows": rows,
            "columns": columns + 2,
            "frames": evidence.frames,
            "first_preview_ms": evidence.first_preview_ms,
            "frame_p95_ms": p95,
            "default_prepare_ms": default_ms,
            "expanded_prepare_ms": expanded_ms,
            "peak_rss_mib": peak,
            "selected_points": 10_000,
            "three_d": three_d,
            "markers_visible": True if three_d else None,
            "view": view,
            "row_identity": True,
            "source_preserved": True,
            "max_rendered_rows": evidence.max_rendered_rows,
        }
        output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=int, nargs=2)
    parser.add_argument("--gui", type=int, nargs=2)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-exploration-benchmark.json")
    )
    parser.add_argument("--three-d", action="store_true")
    parser.add_argument(
        "--view", choices=["scatter", "grid", "comparison"], default="scatter"
    )
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(measure(*args.worker)))
        return
    if args.gui:
        gui_measure(args.gui[0], args.gui[1], args.output, args.three_d, args.view)
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
        "budgets": {
            "default_prepare_ms": DEFAULT_PREPARE_MS,
            "expanded_prepare_ms": EXPANDED_PREPARE_MS,
            "frame_p95_ms": 33,
            "peak_rss_mib": 1024,
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
