"""Native aligned NPZ table, per-column Inspect and fresh-process restoration."""

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
from imgui_bundle import hello_imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.pipeline.operations import Sort


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/tmp/datelier-npz-records"))
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-npz-evidence")
    )
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--view", choices=("table", "heatmap", "full"), default="full")
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.root / "heatmap_record.npz"
    workspace = args.root / "records.datelier"
    if not args.restore:
        (args.root / "prefs.json").unlink(missing_ok=True)
        heatmaps = np.arange(4 * 64 * 96, dtype=np.float32).reshape(4, 64, 96)
        images = np.zeros((4, 32, 48, 3), dtype=np.uint8)
        for row in range(4):
            images[row] = (10 * (row + 1), 5, 9)
        np.savez_compressed(
            source,
            heatmaps=heatmaps,
            labels=np.array([3, 1, 2, 0]),
            scale=np.arange(4, dtype=np.float32),
            images=images,
        )
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    stage = entered = 0
    inspected: list[str] = []

    def frame(
        editor: EditorSession, _tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered
        file = editor.active
        active = file.loader.active
        if active is None:
            return
        age = evidence.frames - entered
        runner = hello_imgui.get_runner_params()
        if stage == 0:
            assert active.dataset.table.columns == [
                "heatmaps",
                "labels",
                "scale",
                "images",
            ]
            assert active.dataset.table.height == 4
            assert file.arrays.store.extractions == 0
            assert file.images.jobs.active is None
            assert file.references.source is None
            if args.restore:
                assert active.dataset.row_ids.to_list() == [3, 1, 2, 0]
                assert file.selection.row_ids == {3}
                assert file.inspect.settings.primary == "images"
                assert "Profiles" in (file.exploration.tab, file.exploration.active_tab)
                # Restoration itself must not decode array grids.
                file.exploration.tab = "Inspect"
                runner.docking_params.focus_dockable_window("Explore")
                stage, entered = 5, evidence.frames
            else:
                file.exploration.tab = "Profiles"
                runner.docking_params.focus_dockable_window("Table")
                stage, entered = 1, evidence.frames
        elif stage == 1 and age > 30:
            if args.view == "table":
                stage = 7
                runner.app_shall_exit = True
                return
            file.editor.request(Sort(("labels",)))
            stage, entered = 2, evidence.frames
        elif stage == 2 and not file.editor.busy and age > 8:
            assert active.dataset.row_ids.to_list() == [3, 1, 2, 0]
            file.inspect.settings = replace(
                file.inspect.settings, gallery=False, primary="heatmaps", focus=0
            )
            file.exploration.tab = "Inspect"
            runner.docking_params.focus_dockable_window("Explore")
            stage, entered = 3, evidence.frames
        elif stage == 3 and age > 15 and file.images.jobs.active is not None:
            image = file.images.jobs.active
            assert image.locator.mapping and image.locator.mapping.member == "heatmaps"
            assert image.locator.origin.row_id == 3
            assert image.pixel(0, 0) == (float(3 * 64 * 96),)
            assert file.arrays.store.extractions == 1
            inspected.append("heatmaps")
            if args.view == "heatmap":
                stage = 7
                runner.app_shall_exit = True
                return
            file.inspect.settings = replace(file.inspect.settings, primary="images")
            stage, entered = 5, evidence.frames
        elif stage == 5 and age > 15 and file.images.jobs.active is not None:
            image = file.images.jobs.active
            if (
                image.locator.mapping is None
                or image.locator.mapping.member != "images"
            ):
                return
            assert image.locator.origin.row_id == 3
            assert image.pixel(0, 0) == (40, 5, 9)
            inspected.append("images")
            if args.restore:
                stage = 7
                runner.app_shall_exit = True
            else:
                file.selection.choose(active.dataset.revision, (3,))
                file.exploration.tab = "Profiles"
                stage, entered = 6, evidence.frames
        elif stage == 6 and age > 8:
            assert file.exploration.active_tab == "Profiles"
            editor.save_workspace(workspace, overwrite=True)
            stage, entered = 8, evidence.frames
        elif stage == 8 and age > 8 and not editor.workspace_jobs.busy:
            assert workspace.exists()
            file.exploration.tab = "Inspect"
            stage, entered = 9, evidence.frames
        elif stage == 9 and age > 8:
            stage = 7
            runner.app_shall_exit = True

    evidence = run_gui(
        None if args.restore else source,
        initial_workspace=workspace if args.restore else None,
        smoke_frames=500,
        on_editor_frame=frame,
        preferences_path=args.root / "prefs.json",
    )
    assert stage == 7, stage
    screenshot(
        args.output
        / (
            "restored.png"
            if args.restore
            else f"{args.view}.png"
            if args.view != "full"
            else "image.png"
        )
    )
    assert before == hashlib.sha256(source.read_bytes()).hexdigest()
    report = {
        "restore": args.restore,
        "rows": 4,
        "columns": ["heatmaps", "labels", "scale", "images"],
        "source_ids": [0, 1, 2, 3] if args.view == "table" else [3, 1, 2, 0],
        "inspected_columns": inspected,
        "lazy_grid_open": True,
        "source_preserved": True,
        "frames": evidence.frames,
        "frame_p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
    }
    (
        args.output / ("restore.json" if args.restore else f"{args.view}.json")
    ).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


def screenshot(path: Path) -> None:
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(path)


if __name__ == "__main__":
    main()
