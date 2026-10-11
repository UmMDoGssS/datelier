"""Declared multi-file comparison responsiveness, retained memory and cleanup gates."""

import gc
import json
import os
import resource
import threading
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from weakref import ref

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui

from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.comparison_settings import (
    ComparisonSettings,
    ComparisonSource,
    Normalization,
)

BUDGETS = {
    "prepare_ms": 2000,
    "frame_p95_ms": 33,
    "peak_rss_mib": 1024,
    "retained_growth_mib": 96,
    "workers": 4,
}


def rss_mib() -> float:
    return (
        int(Path("/proc/self/statm").read_text().split()[1])
        * os.sysconf("SC_PAGE_SIZE")
        / 2**20
    )


def main() -> None:
    stage, cycles, entered = 0, 0, 0
    started = perf_counter()
    prepare_ms: list[float] = []
    baseline = 0.0
    report: dict[str, object] = {}
    closed = []
    with TemporaryDirectory(prefix="datelier-comparison-resources-") as directory:
        root = Path(directory)
        paths = (root / "train.parquet", root / "test.parquet")
        for path, rows, name, scale in zip(
            paths, (100_000, 60_000), ("x", "different"), (1.0, 1.5), strict=True
        ):
            pl.DataFrame(
                {
                    name: np.arange(rows, dtype=np.float64) * scale,
                    "category": [f"c{i % 40}" for i in range(rows)],
                    "extra1": np.arange(rows),
                    "extra2": np.ones(rows),
                }
            ).write_parquet(path)
        original = tuple(path.read_bytes() for path in paths)
        fixture_bytes = sum(path.stat().st_size for path in paths)

        comparison_frames = 0

        def hook(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal \
                stage, \
                cycles, \
                entered, \
                started, \
                baseline, \
                closed, \
                comparison_frames
            if any(k.path[-2:] == ("column-chart", "canvas") for k in probe.targets):
                comparison_frames += 1
            if stage == 0:
                editor.opening.request(paths, editor.active_id)
                stage = 1
            elif stage == 1:
                if len(editor.files) != 2 or any(
                    f.explorer.active is None for f in editor.files
                ):
                    return
                train, test = editor.files
                editor.compare.columns.recipes = (
                    ComparisonSettings(
                        (
                            ComparisonSource(train.identity, "x", "Training"),
                            ComparisonSource(test.identity, "different", "Test"),
                        )
                    ),
                    ComparisonSettings(
                        (
                            ComparisonSource(train.identity, "category", "Training"),
                            ComparisonSource(test.identity, "category", "Test"),
                        )
                    ),
                )
                editor.choose_route("Compare files")
                started = perf_counter()
                stage = 2
            elif stage == 2:
                if (
                    editor.compare.columns.jobs.busy
                    or not editor.compare.columns.jobs.states
                    or any(s.result is None for s in editor.compare.columns.jobs.states)
                ):
                    return
                prepare_ms.append((perf_counter() - started) * 1000)
                for state in editor.compare.columns.jobs.states:
                    assert state.result is not None
                    for series in state.result.series:
                        assert series.counts.sum() == series.included
                        assert len(series.counts) <= 101
                if cycles == 0:
                    baseline = rss_mib()
                if cycles < 20:
                    cycles += 1
                    editor.compare.columns.recipes = tuple(
                        replace(
                            recipe,
                            bins=10 + cycles,
                            category_limit=10 + cycles,
                            normalization=Normalization.COUNT
                            if cycles % 2
                            else Normalization.DENSITY,
                        )
                        for recipe in editor.compare.columns.recipes
                    )
                    started = perf_counter()
                else:
                    stage, entered = 3, evidence.frames
            elif stage == 3:
                if editor.workers.pending or evidence.frames < entered + 30:
                    return
                assert comparison_frames > 20
                gc.collect()
                growth = rss_mib() - baseline
                p95 = float(np.percentile(evidence.frame_intervals_ms, 95))
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
                workers = sum(t.name.startswith("file_") for t in threading.enumerate())
                report.update(
                    budgets=BUDGETS,
                    rows=[100_000, 60_000],
                    columns_per_file=4,
                    comparisons=2,
                    update_cycles=cycles,
                    frames=evidence.frames,
                    comparison_frames=comparison_frames,
                    initial_prepare_ms=prepare_ms[0],
                    max_prepare_ms=max(prepare_ms),
                    frame_p95_ms=p95,
                    peak_rss_mib=peak,
                    retained_growth_mib=growth,
                    workers=workers,
                    outstanding_jobs=editor.workers.pending,
                    fixture_disk_bytes=fixture_bytes,
                )
                assert max(prepare_ms) <= BUDGETS["prepare_ms"], report
                assert p95 <= BUDGETS["frame_p95_ms"], report
                assert peak <= BUDGETS["peak_rss_mib"], report
                assert growth <= BUDGETS["retained_growth_mib"], report
                assert workers <= BUDGETS["workers"], report
                closed = [ref(f) for f in editor.files]
                for identity in tuple(f.identity for f in editor.files):
                    editor.close_file(identity)
                stage, entered = 4, evidence.frames
            elif stage == 4:
                if evidence.frames < entered + 20 or editor.workers.pending:
                    return
                # The closing frame holds its active FileSession until it returns.
                gc.collect()
                report["retained_closed_sessions"] = sum(
                    r() is not None for r in closed
                )
                assert report["retained_closed_sessions"] == 0, report
                assert not editor.compare.columns.jobs.busy
                hello_imgui.get_runner_params().app_shall_exit = True
                stage = 5

        run_gui(smoke_frames=5000, on_probe_frame=hook)
        assert stage == 5, stage
        report["source_bytes_unchanged"] = (
            tuple(path.read_bytes() for path in paths) == original
        )
        assert report["source_bytes_unchanged"]
    report["temporary_directory_removed"] = not root.exists()
    report["worker_threads_after_exit"] = sum(
        t.name.startswith("file_") for t in threading.enumerate()
    )
    assert (
        report["temporary_directory_removed"]
        and report["worker_threads_after_exit"] == 0
    )
    Path("/tmp/datelier-comparison-resources.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
