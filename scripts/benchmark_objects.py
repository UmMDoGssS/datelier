"""Declared structured-source responsiveness, sharing and cleanup budgets."""

import json
import resource
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import enumerate as threads
from time import perf_counter

import numpy as np
from imgui_bundle import hello_imgui

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe

BUDGETS = {
    "source_ms": 5000,
    "view_ms": 3000,
    "frame_p95_ms": 33,
    "peak_rss_mib": 1024,
    "workers": 4,
}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="datelier-object-benchmark-") as directory:
        root = Path(directory)
        source = root / "objects.json"
        source.write_text(
            json.dumps(
                {
                    "records": [
                        {"id": i, "value": i / 10, "label": f"record {i}"}
                        for i in range(50_000)
                    ],
                    "other": {"deep": [None, True, "café"]},
                }
            )
        )
        before = source.read_bytes()
        started = perf_counter()
        stage = 0
        opened = 0.0
        report: dict[str, object] = {"budgets": BUDGETS, "rows": 50_000, "columns": 3}
        owning: EditorController | None = None

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, opened, owning
            owning = editor
            owner = editor.active
            if stage == 0 and owner.loader.active:
                report["source_ms"] = (perf_counter() - started) * 1000
                opened = perf_counter()
                owner.record_views.open(owner, ("records",))
                stage = 1
            elif stage == 1 and owner.record_views.files:
                view = owner.record_views.active(owner)
                assert view.loader.active and owner.loader.active
                assert view.loader.active.row_count == 50_000
                assert (
                    view.loader.active.imported.object_root
                    is owner.loader.active.imported.object_root
                )
                report["view_ms"] = (perf_counter() - opened) * 1000
                stage = 2
            elif stage == 2 and evidence.frames >= 180:
                report["workers"] = sum(t.name.startswith("file_") for t in threads())
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(source, smoke_frames=1200, on_probe_frame=frame)
        assert stage == 2
        report["frames"] = evidence.frames
        report["frame_p95_ms"] = float(np.percentile(evidence.frame_intervals_ms, 95))
        report["peak_rss_mib"] = (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        )
        assert source.read_bytes() == before
        assert owning is not None and owning.closed
        assert not any(t.name.startswith("file_") for t in threads())
        assert all(f.closed and not f.record_views.files for f in owning.files)
        for name, limit in BUDGETS.items():
            value = report[name]
            assert isinstance(value, (int, float)) and value <= limit, (
                name,
                value,
                limit,
            )
        report["source_preserved"] = True
        report["temporary_cleanup"] = True
    assert not root.exists()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
