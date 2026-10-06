"""Declared CPU checkpoint metadata/window resource and source/cleanup gates."""

import argparse
import hashlib
import importlib
import json
import os
import resource
import subprocess
import sys
from math import prod
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import enumerate as threads
from time import perf_counter

import numpy as np
from imgui_bundle import hello_imgui

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.inspection.arrays.settings import SliceSettings
from datelier.inspection.arrays.windows import MAX_SLICE_CELLS
from datelier.io.checkpoints.storage import CheckpointStore

BUDGETS = {
    "metadata_ms": 5000,
    "first_slice_ms": 3000,
    "update_ms": 1000,
    "frame_p95_ms": 33,
    "peak_rss_mib": 1536,
    "retained_logical_bytes": 64 * 1024 * 1024,
    "prepared_bytes": 2 * 1024 * 1024,
    "workers": 4,
}


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def run(source: Path) -> dict[str, object]:
    original = digest(source)
    started = perf_counter()
    prepared_at = 0.0
    stage = updates = completed_at = 0
    times: list[float] = []
    owning: EditorSession | None = None
    store: CheckpointStore | None = None
    numpy_sizes: list[int] = []
    restore_numpy = None
    report: dict[str, object] = {
        "budgets": BUDGETS,
        "selected_shape": [8, 512, 512],
        "unselected_shape": [1024, 1024, 32],
        "window": [128, 128],
    }

    def request(editor: EditorSession, offset: int) -> None:
        nonlocal prepared_at
        editor.active.checkpoints.request(
            SliceSettings(
                "$['state_dict']['cube']",
                (1, 2),
                (offset % 8, 0, 0),
                (offset % 3 * 128, offset % 3 * 128),
                (128, 128),
            )
        )
        prepared_at = perf_counter()

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, updates, completed_at, owning, store, restore_numpy
        owning = editor
        jobs = editor.active.checkpoints
        if stage == 0 and jobs.catalog is not None:
            assert jobs.active is None and jobs.store.loads == 0
            report["metadata_ms"] = (perf_counter() - started) * 1000
            # Instrument the optional boundary after cold metadata import. All
            # NumPy conversions must be selected windows, never the bulk tensor.
            torch = importlib.import_module("torch")
            restore_numpy = torch.Tensor.numpy

            def checked_numpy(value, *args, **kwargs):
                size = prod(tuple(value.shape))
                assert size <= MAX_SLICE_CELLS
                numpy_sizes.append(size)
                return restore_numpy(value, *args, **kwargs)

            torch.Tensor.numpy = checked_numpy
            store = jobs.store
            jobs.set_retention(BUDGETS["retained_logical_bytes"])
            request(editor, 0)
            stage = 1
        elif stage == 1 and jobs.active is not None and not jobs.busy:
            report["first_slice_ms"] = (perf_counter() - prepared_at) * 1000
            completed_at, stage = evidence.frames, 2
        elif stage == 2 and not jobs.busy and evidence.frames - completed_at > 5:
            if updates == 20:
                assert jobs.active and jobs.store.loads == 1
                assert len(numpy_sizes) == 21 and max(numpy_sizes) == MAX_SLICE_CELLS
                report.update(
                    {
                        "loads": jobs.store.loads,
                        "numpy_windows": len(numpy_sizes),
                        "unselected_payload_converted": False,
                        "retained_logical_bytes": jobs.store.stored_bytes,
                        "prepared_bytes": jobs.active.retained_bytes,
                        "workers": sum(t.name.startswith("file_") for t in threads()),
                    }
                )
                hello_imgui.get_runner_params().app_shall_exit = True
                stage = 4
            else:
                request(editor, updates + 1)
                updates += 1
                stage = 3
        elif stage == 3 and not jobs.busy and jobs.active is not None:
            result = jobs.active.view
            plane = result.settings.fixed[0]
            row, column = result.starts
            expected = (
                plane * 512 * 512
                + np.arange(row, row + 128)[:, None] * 512
                + np.arange(column, column + 128)[None, :]
            )
            np.testing.assert_array_equal(result.raw, expected)
            times.append((perf_counter() - prepared_at) * 1000)
            completed_at, stage = evidence.frames, 2

    try:
        evidence = run_gui(source, smoke_frames=1500, on_editor_frame=frame)
    finally:
        if restore_numpy is not None:
            importlib.import_module("torch").Tensor.numpy = restore_numpy
    assert stage == 4, report
    report.update(
        {
            "frames": evidence.frames,
            "update_ms": max(times),
            "frame_p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        }
    )
    for name, limit in BUDGETS.items():
        value = report[name]
        assert isinstance(value, (int, float)) and value <= limit, (name, value, limit)
    assert digest(source) == original
    assert (
        owning is not None
        and owning.closed
        and store is not None
        and store.stored_bytes == 0
    )
    assert not any(t.name.startswith("file_") for t in threads())
    report["source_preserved"] = report["storage_cleanup"] = True
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.source:
        report = run(args.source)
    else:
        with TemporaryDirectory(prefix="datelier-checkpoint-benchmark-") as directory:
            root = Path(directory)
            source = root / "checkpoint.pt"
            # Fixture construction is outside the measured native process.
            torch = importlib.import_module("torch")
            torch.save(
                {
                    "state_dict": {
                        "cube": torch.arange(
                            8 * 512 * 512, dtype=torch.float32
                        ).reshape(8, 512, 512),
                        "unselected": torch.zeros((1024, 1024, 32), dtype=torch.uint8),
                    },
                    "epoch": 7,
                },
                source,
            )
            completed = subprocess.run(
                [sys.executable, __file__, "--source", str(source)],
                check=False,
                capture_output=True,
                text=True,
                env=os.environ.copy(),
            )
            if completed.returncode:
                raise RuntimeError(completed.stderr + completed.stdout)
            report = json.loads(completed.stdout.strip().splitlines()[-1])
        assert not root.exists()
        report["temporary_cleanup"] = True
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
