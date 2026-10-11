"""Declared lazy-array resource, exact-window, retention and cleanup gates."""

import argparse
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
from datelier.inspection.arrays.slices import SliceSettings

BUDGETS = {
    "metadata_ms": 2000,
    "first_slice_ms": 3000,
    "update_ms": 1000,
    "frame_p95_ms": 33,
    "peak_rss_mib": 1024,
    "retained_disk_bytes": 16 * 1024 * 1024,
    "workers": 4,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="datelier-array-benchmark-") as directory:
        root = Path(directory)
        source = root / "arrays.npz"
        chosen = np.arange(8 * 512 * 512, dtype=np.float32).reshape(8, 512, 512)
        np.savez_compressed(
            source, cube=chosen, unselected=np.zeros((1024, 1024, 32), dtype=np.uint8)
        )
        original = source.read_bytes()
        started = perf_counter()
        prepared_at = 0.0
        stage = updates = completed_at = 0
        updates_ms: list[float] = []
        owning: EditorController | None = None
        temporary: Path | None = None
        report: dict[str, object] = {
            "budgets": BUDGETS,
            "selected_shape": [8, 512, 512],
            "unselected_shape": [1024, 1024, 32],
            "window": [128, 128],
        }

        def request(editor: EditorController, offset: int) -> None:
            nonlocal prepared_at
            fixed = (offset % 8, 0, 0)
            editor.active.arrays.request(
                SliceSettings(
                    "cube",
                    (1, 2),
                    fixed,
                    (offset % 3 * 128, offset % 3 * 128),
                    (128, 128),
                )
            )
            prepared_at = perf_counter()

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal owning, temporary, stage, updates, completed_at
            owning = editor
            jobs = editor.active.arrays
            if stage == 0 and jobs.catalog:
                assert jobs.active is None and jobs.store.temporary_path is None
                jobs.store.limit = BUDGETS["retained_disk_bytes"]
                report["metadata_ms"] = (perf_counter() - started) * 1000
                request(editor, 0)
                stage = 1
            elif stage == 1 and jobs.active and not jobs.busy:
                report["first_slice_ms"] = (perf_counter() - prepared_at) * 1000
                temporary = jobs.store.temporary_path
                completed_at = evidence.frames
                stage = 2
            elif stage == 2 and not jobs.busy and evidence.frames - completed_at > 5:
                if updates == 20:
                    assert jobs.catalog and jobs.active
                    member = jobs.catalog.member("cube")
                    assert jobs.store.extractions == 1
                    assert jobs.store.extracted_bytes == member.container_bytes
                    assert jobs.store.stored_bytes == member.container_bytes
                    report["extractions"] = jobs.store.extractions
                    report["extracted_bytes"] = jobs.store.extracted_bytes
                    report["retained_disk_bytes"] = jobs.store.stored_bytes
                    report["unselected_payload_loaded"] = False
                    report["workers"] = sum(
                        t.name.startswith("file_") for t in threads()
                    )
                    hello_imgui.get_runner_params().app_shall_exit = True
                    stage = 4
                else:
                    request(editor, updates + 1)
                    updates += 1
                    stage = 3
            elif stage == 3 and not jobs.busy and jobs.active:
                result = jobs.active
                i = result.settings.fixed[0]
                row, column = result.starts
                np.testing.assert_array_equal(
                    result.raw, chosen[i, row : row + 128, column : column + 128]
                )
                updates_ms.append((perf_counter() - prepared_at) * 1000)
                completed_at = evidence.frames
                stage = 2

        evidence = run_gui(source, smoke_frames=1500, on_probe_frame=frame)
        assert stage == 4
        report["frames"] = evidence.frames
        report["update_ms"] = max(updates_ms)
        report["frame_p95_ms"] = float(np.percentile(evidence.frame_intervals_ms, 95))
        report["peak_rss_mib"] = (
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        )
        for name, limit in BUDGETS.items():
            value = report[name]
            assert isinstance(value, (int, float)) and value <= limit, (
                name,
                value,
                limit,
            )
        assert source.read_bytes() == original
        assert (
            owning is not None
            and owning.closed
            and temporary
            and not temporary.exists()
        )
        assert not any(t.name.startswith("file_") for t in threads())
        report["source_preserved"] = report["temporary_cleanup"] = True
    assert not root.exists()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
