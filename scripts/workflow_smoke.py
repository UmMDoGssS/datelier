"""Personal-use walkthrough in fresh save/reopen GUI processes (also from a wheel)."""

import argparse
import json
import os
import resource
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui

import datelier
from datelier.analysis_types import Algorithm
from datelier.gui import GuiSession, InspectionEvidence, run_gui
from datelier.io.exporting import ExportFormat
from datelier.pipeline.operations import Comparison, Filter, Sort
from datelier.pipeline.types import DerivedColumn


def expected_table(source: Path) -> pl.DataFrame:
    return (
        pl.read_csv(source)
        .sort("x", descending=True)
        .filter(pl.col("x") >= 5)
        .with_columns((pl.col("x") * 2 + pl.col("y")).alias("score"))
    )


def worker(root: Path, restoring: bool) -> None:
    source, workspace = root / "data.csv", root / "session.datelier"
    original = source.read_bytes()
    expected = expected_table(source)
    stage, entered = 0, 0
    started = monotonic()

    def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
        nonlocal stage, entered
        assert monotonic() - started < 90, f"Workflow stalled at stage {stage}"
        active = session.loader.active
        if active is None or session.explorer.busy or session.editor.busy:
            return
        dataset, analysis = active.dataset, session.analysis
        if restoring:
            assert not analysis.jobs.busy and not analysis.jobs.results
            assert dataset.table.equals(expected)
            assert dataset.row_ids.to_list() == list(range(47, 4, -1))
            if stage == 0:
                assert analysis.controls.seed == 17
                assert analysis.controls.features == ["x", "y", "score"]
                assert session.plots.bins == 7
                assert session.editor.pipeline is not None
                assert session.editor.pipeline.cursor == 3
                session.exploration.tab = "Scatter"
                session.selection.choose(dataset.revision, (47,))
                session.exporter.request(dataset, root / "result.csv", ExportFormat.CSV)
                stage = 1
            elif stage == 1 and not session.exporter.busy:
                assert session.exporter.result is not None, session.exporter.message
                assert pl.read_csv(root / "result.csv").equals(expected)
                session.exporter.request(
                    dataset, root / "result.parquet", ExportFormat.PARQUET
                )
                stage = 2
            elif stage == 2 and not session.exporter.busy:
                assert session.exporter.result is not None, session.exporter.message
                assert pl.read_parquet(root / "result.parquet").equals(expected)
                session.exporter.request(
                    dataset, source, ExportFormat.CSV, overwrite=True
                )
                stage = 3
            elif stage == 3 and not session.exporter.busy:
                assert "source files are preserved" in session.exporter.message
                stage, entered = 4, evidence.frames
            elif stage == 4 and evidence.frames > entered + 20:
                assert session.exploration.interaction.selected_points == 1
                assert session.table.selected_visible_rows == 1
                hello_imgui.get_runner_params().app_shall_exit = True
            return
        if stage == 0:
            assert not analysis.jobs.results
            session.editor.request(Sort(("x",), descending=True))
            stage = 1
        elif stage == 1:
            session.editor.request(Filter("x", Comparison.GE, 5))
            stage = 2
        elif stage == 2:
            session.editor.request(DerivedColumn("score", 'col("x") * 2 + col("y")'))
            stage = 3
        elif stage == 3:
            assert dataset.table.equals(expected)
            session.plots.bins = 7
            session.exploration.tab = "Scatter"
            analysis.controls.features = ["x", "y", "score"]
            analysis.controls.seed = 17
            analysis.controls.start(analysis.jobs, dataset, Algorithm.PCA)
            stage = 4
        elif stage == 4 and analysis.plots.active is not None:
            session.selection.choose(dataset.revision, (47,))
            stage, entered = 5, evidence.frames
        elif stage == 5 and evidence.frames > entered + 20:
            assert session.exploration.interaction.selected_points == 1
            analysis.controls.clusters = 2
            analysis.controls.start(analysis.jobs, dataset, Algorithm.KMEANS)
            stage = 6
        elif stage == 6 and Algorithm.KMEANS in analysis.jobs.results:
            session.workspace.path = str(workspace)
            session.workspace.save(session)
            stage = 7
        elif stage == 7 and not session.workspace.jobs.busy:
            assert session.workspace.jobs.saved is not None, (
                session.workspace.jobs.message
            )
            stage, entered = 8, evidence.frames
        elif stage == 8 and evidence.frames > entered + 20:
            assert len(analysis.jobs.results) == 2
            hello_imgui.get_runner_params().app_shall_exit = True

    evidence = run_gui(
        None if restoring else source,
        initial_workspace=workspace if restoring else None,
        smoke_frames=10_000,
        on_frame=frame,
    )
    assert stage == (4 if restoring else 8), stage
    assert source.read_bytes() == original
    p95 = float(np.percentile(evidence.frame_intervals_ms, 95))
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    worker_peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
    assert p95 <= 33 and peak <= 1024 and peak + worker_peak <= 2048
    name = "reopen" if restoring else "save"
    assert datelier.__file__ is not None
    pixels = hello_imgui.final_app_window_screenshot()
    height, width = pixels.shape[:2]
    (root / f"{name}.ppm").write_bytes(
        f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
    )
    (root / f"{name}.json").write_text(
        json.dumps(
            {
                "frames": evidence.frames,
                "wall_seconds": monotonic() - started,
                "frame_p95_ms": p95,
                "parent_peak_mib": peak,
                "worker_peak_mib": worker_peak,
                "source_preserved": True,
                "linked_selection": True,
                "implicit_ml_runs": 0,
                "explicit_ml_runs": 0 if restoring else 2,
                "imported_package": str(Path(datelier.__file__).resolve()),
            },
            indent=2,
        )
        + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=["save", "reopen"])
    parser.add_argument("--root", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-workflow.json")
    )
    args = parser.parse_args()
    if args.worker:
        if args.root is None:
            parser.error("--worker requires --root")
        worker(args.root, args.worker == "reopen")
        return
    with TemporaryDirectory(prefix="datelier-workflow-") as folder:
        root = Path(folder)
        pl.DataFrame(
            {
                "x": range(48),
                "y": [None if i == 9 else float(np.sin(i)) for i in range(48)],
                "group": [f"group_{i % 3}" for i in range(48)],
            }
        ).write_csv(root / "data.csv")
        reports = {}
        for name in ("save", "reopen"):
            subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker",
                    name,
                    "--root",
                    str(root),
                ],
                check=True,
                timeout=100,
            )
            reports[name] = json.loads((root / f"{name}.json").read_text())
            args.output.with_name(f"{args.output.stem}-{name}.ppm").write_bytes(
                (root / f"{name}.ppm").read_bytes()
            )
        args.output.write_text(
            json.dumps(
                {
                    "platform": sys.platform,
                    "python": sys.version,
                    "polars_threads": pl.thread_pool_size(),
                    "software_gl": os.environ.get("LIBGL_ALWAYS_SOFTWARE"),
                    "fixture": "48 rows; Int64 x, Float64 y (one null), String group",
                    "processes": reports,
                },
                indent=2,
            )
            + "\n"
        )
        print(args.output.read_text())


if __name__ == "__main__":
    main()
