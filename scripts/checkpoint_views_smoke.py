"""Native array fixed-index input, explicit slicing and fresh-process restore."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.checkpoints.view import CheckpointView
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.inspection.arrays.slices import SliceSettings


def run(root: Path, mode: str) -> dict[str, object]:
    source, workspace = root / "checkpoint.pt", root / "checkpoint.datelier"
    view: CheckpointView | None = None
    index_pixel = (0.0, 0.0)
    original_show = CheckpointView.show
    original_input = imgui.input_int
    stage = entered = 0
    observed: dict[str, object] = {}
    metadata_only = False

    def show(self: CheckpointView, owner) -> None:
        nonlocal view
        original_show(self, owner)
        view = self

    def input_int(label: str, value: int, *args, **kwargs):
        nonlocal index_pixel
        result = original_input(label, value, *args, **kwargs)
        if label.startswith("Tensor axis 0 fixed"):
            lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
            index_pixel = (lo.x + 40, (lo.y + hi.y) / 2)
        return result

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered, metadata_only
        file = editor.active
        jobs = file.checkpoints
        io = imgui.get_io()
        age = evidence.frames - entered
        observed.update(
            stage=stage,
            message=jobs.message,
            fixed=jobs.settings.fixed,
            source=file.loader.status.message,
        )
        if view is None or jobs.catalog is None:
            return
        if stage == 0 and age > 12 and view.combo_pixel != (0, 0):
            assert jobs.active is None and jobs.store.loads == 0
            metadata_only = True
            if mode == "restore":
                assert (
                    jobs.settings.member == "$['state_dict']['cube']"
                    and jobs.settings.fixed[0] == 1
                )
                io.mouse_pos = imgui.ImVec2(*view.prepare_pixel)
                io.want_set_mouse_pos = True
                stage, entered = 7, evidence.frames
            else:
                io.mouse_pos = imgui.ImVec2(*view.combo_pixel)
                io.want_set_mouse_pos = True
                stage, entered = 20, evidence.frames
        elif stage == 20 and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = 21, evidence.frames
        elif stage == 21 and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = 22, evidence.frames
        elif stage == 22 and "$['state_dict']['cube']" in view.node_pixels and age > 3:
            io.mouse_pos = imgui.ImVec2(*view.node_pixels["$['state_dict']['cube']"])
            io.want_set_mouse_pos = True
            stage, entered = 23, evidence.frames
        elif stage == 23 and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = 24, evidence.frames
        elif stage == 24 and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = 25, evidence.frames
        elif stage == 25 and age > 5 and index_pixel != (0, 0):
            assert jobs.settings.member == "$['state_dict']['cube']"
            io.mouse_pos = imgui.ImVec2(*index_pixel)
            io.want_set_mouse_pos = True
            stage, entered = 1, evidence.frames
        elif stage == 1 and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = 2, evidence.frames
        elif stage == 2 and age > 3:
            io.add_mouse_button_event(0, False)
            io.add_key_event(imgui.Key.left_ctrl, True)
            io.add_key_event(imgui.Key.a, True)
            stage, entered = 3, evidence.frames
        elif stage == 3 and age > 3:
            io.add_key_event(imgui.Key.a, False)
            io.add_key_event(imgui.Key.left_ctrl, False)
            io.add_input_characters_utf8("1")
            stage, entered = 4, evidence.frames
        elif stage == 4 and age > 3:
            io.add_key_event(imgui.Key.enter, True)
            stage, entered = 5, evidence.frames
        elif stage == 5 and age > 3:
            io.add_key_event(imgui.Key.enter, False)
            stage, entered = 6, evidence.frames
        elif (
            stage == 6
            and jobs.settings.fixed
            and jobs.settings.fixed[0] == 1
            and age > 3
        ):
            io.mouse_pos = imgui.ImVec2(*view.prepare_pixel)
            io.want_set_mouse_pos = True
            stage, entered = 7, evidence.frames
        elif stage == 7 and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = 8, evidence.frames
        elif stage == 8 and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = 9, evidence.frames
        elif stage == 9 and jobs.active and file.array_view.plot_frames > 5:
            np.testing.assert_array_equal(
                jobs.active.view.raw, np.arange(24).reshape(2, 3, 4)[1]
            )
            assert jobs.store.loads == 1
            if mode == "save":
                jobs.request(SliceSettings("$['bf16']", (0,), (0,), (0,), (128,)))
                stage, entered = 13, evidence.frames
            else:
                stage, entered = 11, evidence.frames
        elif stage == 10 and not editor.workspace_jobs.busy:
            assert editor.workspace_jobs.saved
            stage, entered = 11, evidence.frames
        elif (
            stage == 13
            and jobs.active
            and jobs.active.view.settings.member == "$['bf16']"
            and age > 5
        ):
            assert jobs.active.storage and jobs.active.dtype == "torch.bfloat16"
            np.testing.assert_array_equal(jobs.active.view.raw, [1.5, -2.25])
            assert jobs.active.storage.raw.dtype == np.uint16
            jobs.request(
                SliceSettings(
                    "$['state_dict']['cube']", (1, 2), (1, 0, 0), (0, 0), (128, 128)
                )
            )
            stage, entered = 15, evidence.frames
        elif (
            stage == 15
            and jobs.active
            and jobs.active.view.settings.member == "$['state_dict']['cube']"
            and age > 5
        ):
            assert jobs.store.loads == 1
            editor.save_workspace(workspace)
            stage, entered = 10, evidence.frames
        elif stage == 11 and age > 5:
            stage = 12
            hello_imgui.get_runner_params().app_shall_exit = True

    with (
        patch.object(CheckpointView, "show", show),
        patch.object(imgui, "input_int", input_int),
    ):
        evidence = run_gui(
            source if mode == "save" else None,
            initial_workspace=workspace if mode == "restore" else None,
            smoke_frames=500,
            on_editor_frame=frame,
        )
    assert stage == 12, observed
    if mode == "save":
        Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
            root / "checkpoint.png"
        )
    assert view is not None
    return {
        "mode": mode,
        "frames": evidence.frames,
        "metadata_only_open": metadata_only,
        "native_prepare": True,
        "native_fixed_index": mode == "save",
        "native_tensor_navigation": mode == "save",
        "frame_p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["save", "restore"])
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mode:
        assert args.root is not None
        print(json.dumps(run(args.root, args.mode)))
        return
    with TemporaryDirectory(prefix="datelier-checkpoint-smoke-") as directory:
        root = Path(directory)
        source = root / "checkpoint.pt"
        # Fixture creation is the only script-side optional library boundary.
        import importlib

        torch = importlib.import_module("torch")
        torch.save(
            {
                "vector": torch.arange(3, dtype=torch.float32),
                "state_dict": {"cube": torch.arange(24).reshape(2, 3, 4)},
                "bf16": torch.tensor([1.5, -2.25], dtype=torch.bfloat16),
                "epoch": 7,
            },
            source,
        )
        original = source.read_bytes()
        reports: list[object] = []
        for mode in ("save", "restore"):
            completed = subprocess.run(
                [sys.executable, __file__, "--mode", mode, "--root", str(root)],
                check=False,
                capture_output=True,
                text=True,
                env=os.environ.copy(),
            )
            if completed.returncode:
                raise RuntimeError(completed.stderr + completed.stdout)
            reports.append(json.loads(completed.stdout.strip().splitlines()[-1]))
        assert source.read_bytes() == original
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.with_suffix(".png").write_bytes(
                (root / "checkpoint.png").read_bytes()
            )
        report = {
            "processes": reports,
            "source_preserved": True,
            "temporary_cleanup": True,
        }
    assert not root.exists()
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
