"""Native mapping confirmation, linked row/payload preview and deferred reopen."""

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
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.pipeline.operations import Sort


def run(root: Path, mode: str) -> dict[str, object]:
    source, workspace = root / "records.npz", root / "records.datelier"
    stage = entered = 0
    target = (0.0, 0.0)
    deferred_pixel = (0.0, 0.0)
    observed: dict[str, object] = {}
    plot_frames = 0
    original_button = imgui.button

    def button(label: str, *args, **kwargs):
        nonlocal deferred_pixel
        result = original_button(label, *args, **kwargs)
        if label == "Prepare saved array records":
            lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
            deferred_pixel = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
        return result

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered, target, plot_frames
        owner = editor.active
        view = owner.record_views.active(owner)
        controls = owner.array_mapping
        io = imgui.get_io()
        age = evidence.frames - entered
        observed.update(
            stage=stage,
            frames=evidence.frames,
            mapping=controls.message,
            source=owner.loader.status.message,
            views=len(owner.record_views.files),
            deferred=view.deferred is not None,
            payload=view.arrays.message,
            selection=tuple(view.selection.row_ids),
            source_index=view.array_records.source_index,
            prepare_pixel=view.array_records.prepare_pixel,
            target=target,
        )

        def aim(pixel: tuple[float, float], next_stage: int) -> None:
            nonlocal target, stage, entered
            target = pixel
            io.mouse_pos = imgui.ImVec2(*pixel)
            io.want_set_mouse_pos = True
            stage, entered = next_stage, evidence.frames

        if stage == 0 and age > 12 and owner.arrays.catalog is not None:
            assert owner.arrays.store.extractions == 0
            if mode == "restore":
                assert view.deferred and view.deferred.file.selection == (3,)
                assert (
                    view.loader.active is None
                    and owner.arrays.store.temporary_path is None
                )
                if deferred_pixel != (0, 0):
                    aim(deferred_pixel, 11)
            elif controls.configure_pixel != (0, 0):
                assert not owner.record_views.files
                aim(controls.configure_pixel, 1)
        elif stage in (1, 4, 7, 11, 14) and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = stage + 1, evidence.frames
        elif stage in (2, 5, 8, 12, 15) and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = stage + 1, evidence.frames
        elif stage == 3 and controls.draft is not None and age > 3:
            assert owner.arrays.store.extractions == 0 and not owner.record_views.files
            assert controls.draft.record_axis == 0 and controls.draft.channel_axis == 3
            assert controls.draft.supporting[0].member == "labels"
            if controls.confirm_pixel != (0, 0):
                aim(controls.confirm_pixel, 4)
        elif stage == 6 and view is not owner and view.loader.active is not None:
            assert owner.arrays.store.extractions == 1  # labels only
            assert (
                view.arrays.store is owner.arrays.store and view.arrays.active is None
            )
            view.editor.request(Sort(("labels",)))
            stage, entered = 10, evidence.frames
        elif (
            stage == 10
            and age > 5
            and not view.editor.busy
            and view.table.first_row_id == 1
            and 3 in view.table.row_pixels
        ):
            assert view.loader.active
            assert view.loader.active.dataset.row_ids.to_list() == [1, 3, 0, 2]
            aim(view.table.row_pixels[3], 7)
        elif stage == 9 and view.selection.row_ids == {3}:
            page = view.array_records.fields.get(0)
            if (
                page
                and page.cards[0].row_id == 3
                and view.array_records.prepare_pixel != (0, 0)
            ):
                assert (
                    next(f.text for f in page.cards[0].fields if f.name == "labels")
                    == "5"
                )
                aim(view.array_records.prepare_pixel, 14)
        elif stage == 13 and view.loader.active is not None:
            assert view.deferred is None and view.selection.row_ids == {3}
            assert view.loader.active.dataset.row_ids.to_list() == [1, 3, 0, 2]
            assert view.arrays.active is None  # scalar preparation did not open images
            if view.array_records.prepare_pixel != (0, 0) and age > 3:
                aim(view.array_records.prepare_pixel, 14)
        elif (
            stage == 16
            and view.arrays.active is not None
            and age > 6
            and view.array_view.plot_frames > 5
        ):
            np.testing.assert_array_equal(
                view.arrays.active.raw,
                np.arange(4 * 5 * 6 * 3).reshape(4, 5, 6, 3)[3, :, :, 0],
            )
            assert view.arrays.active.settings.fixed[0] == 3
            assert view.array_view.plot_frames > 5
            plot_frames = view.array_view.plot_frames
            if mode == "save":
                editor.save_workspace(workspace)
                stage, entered = 17, evidence.frames
            else:
                stage, entered = 18, evidence.frames
        elif stage == 17 and not editor.workspace_jobs.busy:
            assert editor.workspace_jobs.saved
            stage, entered = 18, evidence.frames
        elif stage == 18 and age > 5:
            stage = 19
            hello_imgui.get_runner_params().app_shall_exit = True

    with patch.object(imgui, "button", button):
        evidence = run_gui(
            source if mode == "save" else None,
            initial_workspace=workspace if mode == "restore" else None,
            smoke_frames=500,
            on_editor_frame=frame,
        )
    if stage != 19:
        Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
            "/tmp/datelier-array-records-failed.png"
        )
    assert stage == 19, observed
    if mode == "save":
        Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
            root / "records.png"
        )
    return {
        "mode": mode,
        "frames": evidence.frames,
        "native_confirmation": mode == "save",
        "native_linked_selection": mode == "save",
        "metadata_only_reopen": mode == "restore",
        "native_explicit_payload": True,
        "plot_frames": plot_frames,
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
    with TemporaryDirectory(prefix="datelier-array-records-") as directory:
        root = Path(directory)
        source = root / "records.npz"
        np.savez_compressed(
            source,
            images=np.arange(4 * 5 * 6 * 3).reshape(4, 5, 6, 3),
            labels=np.array([8, 3, 9, 5]),
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
                (root / "records.png").read_bytes()
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
