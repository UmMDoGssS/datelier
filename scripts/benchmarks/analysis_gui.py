"""Live default analysis jobs while inspecting large/wide source tables."""

import argparse
import json
import resource
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import cast

import numpy as np
from imgui_bundle import hello_imgui
from numpy.typing import NDArray

from datelier.analysis.types import Algorithm, ClusteringResult
from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from scripts.support.tables import make_table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument("--columns", type=int, default=6)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    algorithms = [Algorithm.PCA, Algorithm.KMEANS, Algorithm.TSNE, Algorithm.UMAP]
    stage, index, entered = 0, 0, 0
    started = 0.0
    timings: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="datelier-analysis-gui-") as folder:
        source = Path(folder) / "source.csv"
        make_table(args.rows, args.columns).write_csv(source)
        original = source.stat()

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            session = editor.current
            nonlocal stage, index, entered, started
            active, dashboard = session.loader.active, session.explorer.active
            if active is None or dashboard is None:
                return
            jobs = session.analysis.jobs
            if stage == 0:
                assert not jobs.busy and not jobs.results
                session.analysis.controls.features = [
                    f"feature_{i}" for i in range(args.columns)
                ]
                editor.choose_route("Relationships")
                stage = 1
            if stage == 1:
                started = perf_counter()
                session.analysis.controls.start(jobs, active.dataset, algorithms[index])
                assert not session.analysis.controls.error
                stage = 2
            elif stage == 2 and not jobs.busy:
                result = jobs.results.get(algorithms[index])
                if result is None:
                    raise RuntimeError(jobs.message)
                session.open_analysis_result(algorithms[index])
                if isinstance(result, ClusteringResult):
                    if dashboard.scatters[0].colors is None:
                        return
                elif (
                    session.analysis.plots.active is None
                    or session.analysis.plots.active.x_name != f"{algorithms[index]} 1"
                ):
                    return
                assert result.revision == active.dataset.revision
                timings.append(
                    {
                        "algorithm": str(algorithms[index]),
                        "wall_seconds": perf_counter() - started,
                        "sampled_rows": result.provenance.input.sampled_rows,
                        "fit_seconds": result.provenance.runtime_seconds,
                    }
                )
                stage, entered = 3, evidence.frames
            elif stage == 3 and evidence.frames > entered + 20:
                index += 1
                if index == len(algorithms):
                    hello_imgui.get_runner_params().app_shall_exit = True
                else:
                    stage = 1

        evidence = run_gui(source, smoke_frames=15000, on_probe_frame=frame)
        assert index == len(algorithms)
        parent = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        child = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
        p95 = float(np.percentile(evidence.frame_intervals_ms, 95))
        after = source.stat()
        assert (original.st_size, original.st_mtime_ns) == (
            after.st_size,
            after.st_mtime_ns,
        )
        report = {
            "rows": args.rows,
            "features": args.columns,
            "frames": evidence.frames,
            "frame_p95_ms": p95,
            "parent_peak_mib": parent,
            "worker_peak_mib": child,
            "combined_peak_upper_bound_mib": parent + child,
            "memory_budget_mib": 2048,
            "memory_passed": parent + child <= 2048,
            "frame_budget_passed": p95 <= 33,
            "explicit_jobs": timings,
            "source_preserved": True,
        }
        args.output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        h, w = pixels.shape[:2]
        args.output.write_bytes(
            f"P6\n{w} {h}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        print(json.dumps(report))
        assert report["memory_passed"] and report["frame_budget_passed"]


if __name__ == "__main__":
    main()
