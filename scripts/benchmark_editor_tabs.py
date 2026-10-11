"""Two-file responsiveness and repeated-tab resource acceptance on Linux."""

import gc
import json
import os
import resource
import threading
import weakref
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui

from datelier.application.editor import EditorController
from datelier.application.file import FileController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe

BUDGETS = {
    "preview_ms": 2000,
    "frame_p95_ms": 33,
    "peak_rss_mib": 1024,
    "retained_growth_mib": 96,
    "close_ms": 33,
    "workers": 4,
}


def rss_mib() -> float:
    pages = int(Path("/proc/self/statm").read_text().split()[1])
    return pages * os.sysconf("SC_PAGE_SIZE") / 2**20


def has_preview(file: FileController, probe: GuiProbe) -> bool:
    return any(
        key.scope.file_id == file.identity
        and "rows" in key.path
        and key.path[-2:] == ("source", "select")
        for key in probe.targets
    )


def main() -> None:
    stage, cycles, entered = 0, 0, 0
    current: FileController | None = None
    closed: list[weakref.ReferenceType[FileController]] = []
    preview_ms: list[float] = []
    close_ms: list[float] = []
    baseline = 0.0
    created = perf_counter()
    report: dict[str, object] = {}
    with TemporaryDirectory(prefix="datelier-tab-resources-") as directory:
        root = Path(directory)
        train, test = root / "train.parquet", root / "test.parquet"
        pl.DataFrame(
            {f"x{i}": np.arange(100_000, dtype=np.float64) * (i + 1) for i in range(8)}
        ).write_parquet(train)
        pl.DataFrame(
            {f"y{i}": np.arange(100_000, dtype=np.float64) * (i + 2) for i in range(8)}
        ).write_parquet(test)
        fixture_bytes = train.stat().st_size + test.stat().st_size
        originals = (train.read_bytes(), test.read_bytes())

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, cycles, entered, current, baseline, created
            if stage == 0:
                if editor.active.explorer.active is None or not has_preview(
                    editor.active, probe
                ):
                    return
                preview_ms.append((perf_counter() - created) * 1000)
                created = perf_counter()
                current = editor.new_file(test)
                stage = 1
            elif stage == 1:
                assert current is not None
                if current.explorer.active is None or not has_preview(current, probe):
                    return
                preview_ms.append((perf_counter() - created) * 1000)
                baseline = rss_mib()
                created = perf_counter()
                current = editor.new_file(train)
                stage = 2
            elif stage == 2:
                assert current is not None
                if current.explorer.busy or not has_preview(current, probe):
                    return
                preview_ms.append((perf_counter() - created) * 1000)
                assert current.pages.page_count <= 4
                closed.append(weakref.ref(current))
                started = perf_counter()
                editor.close_file(current.identity)
                close_ms.append((perf_counter() - started) * 1000)
                current = None
                cycles += 1
                if cycles < 30:
                    created = perf_counter()
                    current = editor.new_file(train)
                else:
                    stage, entered = 3, evidence.frames
            elif stage == 3:
                if editor.workers.pending or evidence.frames < entered + 20:
                    return
                gc.collect()
                alive = sum(reference() is not None for reference in closed)
                growth = rss_mib() - baseline
                workers = sum(
                    thread.name.startswith("file_") for thread in threading.enumerate()
                )
                p95 = float(np.percentile(evidence.frame_intervals_ms, 95))
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
                report.update(
                    budgets=BUDGETS,
                    rows_per_file=100_000,
                    numeric_columns=8,
                    cycles=cycles,
                    frames=evidence.frames,
                    initial_preview_ms=preview_ms[:2],
                    max_cycle_preview_ms=max(preview_ms[2:]),
                    frame_p95_ms=p95,
                    peak_rss_mib=peak,
                    baseline_rss_mib=baseline,
                    retained_growth_mib=growth,
                    max_close_ms=max(close_ms),
                    workers=workers,
                    outstanding_jobs=editor.workers.pending,
                    retained_closed_sessions=alive,
                    fixture_disk_bytes=fixture_bytes,
                )
                assert max(preview_ms) <= BUDGETS["preview_ms"], report
                assert p95 <= BUDGETS["frame_p95_ms"], report
                assert peak <= BUDGETS["peak_rss_mib"], report
                assert growth <= BUDGETS["retained_growth_mib"], report
                assert max(close_ms) <= BUDGETS["close_ms"], report
                assert workers <= BUDGETS["workers"] and alive == 0, report
                hello_imgui.get_runner_params().app_shall_exit = True
                stage = 4

        created = perf_counter()
        run_gui(train, smoke_frames=10_000, on_probe_frame=frame)
        assert stage == 4, (stage, cycles)
        report["source_bytes_unchanged"] = (
            train.read_bytes(),
            test.read_bytes(),
        ) == originals
        assert report["source_bytes_unchanged"]
    report["temporary_directory_removed"] = not root.exists()
    report["worker_threads_after_exit"] = sum(
        thread.name.startswith("file_") for thread in threading.enumerate()
    )
    assert (
        report["temporary_directory_removed"]
        and report["worker_threads_after_exit"] == 0
    )
    Path("/tmp/datelier-tab-resources.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
