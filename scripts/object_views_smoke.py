"""Native object selection/extraction and fresh-process named view restoration."""

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
from datelier.gui.file_session import FileSession
from datelier.gui.objects.browser import ObjectBrowser
from datelier.gui.tabs import EditorTabs
from datelier.pipeline.operations import Sort


def run(root: Path, mode: str) -> dict[str, object]:
    source = root / "objects.json"
    workspace = root / "objects.datelier"
    state: dict[str, object] = {}
    browser: ObjectBrowser | None = None
    original = ObjectBrowser.show
    stage = entered = 0
    target = (0.0, 0.0)

    def show(self: ObjectBrowser, owner: FileSession) -> None:
        nonlocal browser
        original(self, owner)
        browser = self

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered, target
        owner = editor.active
        views = owner.record_views
        io = imgui.get_io()
        age = evidence.frames - entered
        state.update(
            stage=stage,
            phase=str(owner.loader.status.phase),
            message=owner.loader.status.message,
            views=len(views.files),
            view_message=views.message,
            path=repr(views.path),
        )
        if mode == "restore":
            if owner.loader.active and views.files:
                view = views.active(owner)
                assert owner.loader.active.imported.object_root is not None
                assert view.loader.active and view.editor.pipeline
                assert view.view_name == "$['records']"
                assert view.loader.active.dataset.row_ids.to_list() == [1, 0]
                assert view.selection.row_ids == {1}
                assert views.path == ("records",)
                assert view.editor.pipeline.can_undo and not view.analysis.jobs.results
                if evidence.frames > 15:
                    hello_imgui.get_runner_params().app_shall_exit = True
                    stage = 10
            return
        if browser is None:
            return
        if stage == 0 and age > 10 and ("records",) in browser.node_pixels:
            target = browser.node_pixels[("records",)]
            io.mouse_pos = imgui.ImVec2(*target)
            io.want_set_mouse_pos = True
            stage, entered = 1, evidence.frames
        elif stage == 1 and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = 2, evidence.frames
        elif stage == 2 and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = 3, evidence.frames
        elif (
            stage == 3
            and age > 3
            and views.path == ("records",)
            and browser.open_pixel != (0, 0)
        ):
            target = browser.open_pixel
            io.mouse_pos = imgui.ImVec2(*target)
            io.want_set_mouse_pos = True
            stage, entered = 4, evidence.frames
        elif stage == 4 and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = 5, evidence.frames
        elif stage == 5 and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = 6, evidence.frames
        elif stage == 6 and views.files:
            view = views.active(owner)
            assert view.loader.active
            view.editor.request(Sort(("value",)))
            stage, entered = 7, evidence.frames
        elif stage == 7 and not views.active(owner).editor.busy:
            view = views.active(owner)
            assert view.loader.active
            view.selection.choose(view.loader.active.dataset.revision, [1])
            assert view.loader.active.dataset.row_ids.to_list() == [1, 0]
            editor.save_workspace(workspace)
            stage, entered = 8, evidence.frames
        elif stage == 8 and not editor.workspace_jobs.busy and age > 5:
            assert editor.workspace_jobs.saved is not None
            stage = 10
            hello_imgui.get_runner_params().app_shall_exit = True

    with patch.object(ObjectBrowser, "show", show):
        evidence = run_gui(
            source if mode == "save" else None,
            initial_workspace=workspace if mode == "restore" else None,
            smoke_frames=400,
            on_editor_frame=frame,
        )
    assert stage == 10, state
    if mode == "save":
        Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
            root / "objects.png"
        )
    return {
        "mode": mode,
        "frames": evidence.frames,
        "native_node_and_extract": mode == "save",
        "restored_named_view": mode == "restore",
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
    with TemporaryDirectory(prefix="datelier-objects-") as directory:
        root = Path(directory)
        source = root / "objects.json"
        source.write_text(
            '{"records":[{"id":7,"value":3.5},{"id":3,"value":1.5}],"nested":{"empty":[]}}'
        )
        before = source.read_bytes()
        reports: list[object] = []
        for mode in ("save", "restore"):
            completed = subprocess.run(
                [sys.executable, __file__, "--mode", mode, "--root", str(root)],
                check=True,
                capture_output=True,
                text=True,
                env=os.environ.copy(),
            )
            reports.append(json.loads(completed.stdout.strip().splitlines()[-1]))
        assert source.read_bytes() == before
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.with_suffix(".png").write_bytes(
                (root / "objects.png").read_bytes()
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
