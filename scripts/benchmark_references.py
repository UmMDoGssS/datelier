"""Declared nearby-reference latency, retention, frame and closure gates."""

import gc
import hashlib
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
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs

BUDGETS = {
    "metadata_ms": 2000,
    "index_ms": 5000,
    "preview_ms": 2000,
    "frame_p95_ms": 33,
    "peak_rss_mib": 768,
    "retained_growth_mib": 32,
    "cpu_bytes": 2 * 1048576,
    "gpu_bytes": 1048576,
    "workers": 4,
}


def rss_mib() -> float:
    return (
        int(Path("/proc/self/statm").read_text().split()[1])
        * os.sysconf("SC_PAGE_SIZE")
        / 2**20
    )


def main() -> None:
    report: dict[str, object] = {}
    with TemporaryDirectory(prefix="datelier-reference-resources-") as directory:
        root = Path(directory)
        data = root / "data"
        data.mkdir()
        images = root / "images"
        images.mkdir()
        for i in range(1000):
            Image.new("RGB", (256, 128), (i % 255, 100, 180)).save(images / f"{i}.png")
        source = data / "records.parquet"
        pl.DataFrame(
            {
                "id": range(100_000),
                "image": [f"{i % 1000}.png" for i in range(100_000)],
                "metric": np.arange(100_000, dtype=np.float64),
                "group": [f"c{i % 20}" for i in range(100_000)],
            }
        ).write_parquet(source)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        fixture_bytes = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
        started = perf_counter()
        metadata_ms = index_ms = preview_ms = None
        stage = cycles = entered = 0
        baseline = 0.0
        previews: list[float] = []
        closed = []

        def frame(
            editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
        ) -> None:
            nonlocal \
                stage, \
                cycles, \
                entered, \
                metadata_ms, \
                index_ms, \
                preview_ms, \
                baseline, \
                closed
            file = editor.active
            elapsed = (perf_counter() - started) * 1000
            if file.loader.active and metadata_ms is None:
                metadata_ms = elapsed
                file.references.configure(
                    replace(
                        file.references.settings,
                        cpu_bytes=BUDGETS["cpu_bytes"],
                        gpu_bytes=BUDGETS["gpu_bytes"],
                    )
                )
            if file.references.index and index_ms is None:
                index_ms = elapsed
            if file.reference_view.preview_frames and preview_ms is None:
                preview_ms = elapsed
            if (
                stage == 0
                and index_ms is not None
                and preview_ms is not None
                and evidence.frames > 20
            ):
                baseline = rss_mib()
                stage = 1
            elif stage == 1 and file.reference_view.preview_frames:
                previews.append(elapsed)
                if cycles < 20:
                    cycles += 1
                    file.table.target_row = cycles * 4500 + 1
                    file.table.jump = True
                    stage, entered = 2, evidence.frames
                else:
                    stage, entered = 3, evidence.frames
            elif (
                stage == 2
                and evidence.frames > entered + 12
                and file.table.first_visible_row >= cycles * 4500
            ):
                stage = 1
            elif (
                stage == 3
                and evidence.frames > entered + 20
                and not editor.workers.pending
            ):
                gc.collect()
                p95 = float(np.percentile(evidence.frame_intervals_ms, 95))
                peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
                growth = rss_mib() - baseline
                workers = sum(t.name.startswith("file_") for t in threading.enumerate())
                report.update(
                    budgets=BUDGETS,
                    rows=100_000,
                    assets=1000,
                    metadata_ms=metadata_ms,
                    index_ms=index_ms,
                    preview_ms=preview_ms,
                    frames=evidence.frames,
                    scroll_cycles=cycles,
                    frame_p95_ms=p95,
                    peak_rss_mib=peak,
                    retained_growth_mib=growth,
                    cpu_bytes=file.references.retained_bytes,
                    gpu_bytes=file.reference_view.textures.retained_bytes,
                    workers=workers,
                    fixture_disk_bytes=fixture_bytes,
                )
                assert (
                    metadata_ms is not None and metadata_ms <= BUDGETS["metadata_ms"]
                ), report
                assert index_ms is not None and index_ms <= BUDGETS["index_ms"], report
                assert preview_ms is not None and preview_ms <= BUDGETS["preview_ms"], (
                    report
                )
                assert (
                    p95 <= BUDGETS["frame_p95_ms"]
                    and peak <= BUDGETS["peak_rss_mib"]
                    and growth <= BUDGETS["retained_growth_mib"]
                ), report
                assert (
                    file.references.retained_bytes <= BUDGETS["cpu_bytes"]
                    and file.reference_view.textures.retained_bytes
                    <= BUDGETS["gpu_bytes"]
                ), report
                assert workers <= BUDGETS["workers"], report
                closed = [ref(f) for f in editor.files]
                for identity in tuple(f.identity for f in editor.files):
                    editor.close_tab(identity)
                stage, entered = 4, evidence.frames
            elif (
                stage == 4
                and evidence.frames > entered + 20
                and not editor.workers.pending
            ):
                gc.collect()
                assert not any(r() for r in closed)
                report["retained_closed_sessions"] = 0
                report["outstanding_jobs"] = editor.workers.pending
                stage = 5
                hello_imgui.get_runner_params().app_shall_exit = True

        run_gui(source, smoke_frames=3000, on_editor_frame=frame)
        assert stage == 5, (stage, report)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    report.update(
        source_preserved=True,
        temporary_directory_removed=not root.exists(),
        worker_threads_after_exit=sum(
            t.name.startswith("file_") for t in threading.enumerate()
        ),
    )
    assert (
        report["temporary_directory_removed"]
        and report["worker_threads_after_exit"] == 0
    )
    Path("/tmp/datelier-reference-resources.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
