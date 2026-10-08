"""Native missing/changed-source recovery, idle reopen and legacy migration."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

import numpy as np
from audio_smoke_controls import NativeControls
from imgui_bundle import hello_imgui
from multimodal_smoke import layout
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.file_session import FileSession
from datelier.gui.tabs import EditorTabs
from datelier.workspace.session_storage import read_session_workspace
from datelier.workspace.storage import save_workspace


def run(root: Path, output: Path, mode: str) -> dict[str, object]:
    controls = NativeControls()
    workspace = root / (
        "legacy.datelier"
        if mode == "legacy"
        else "recovered.datelier"
        if mode == "reopened"
        else "session.datelier.json"
    )
    report: dict[str, object] = {"mode": mode, "hidden": True}
    stage = entered = 0
    action = 0
    commands = [
        f"Replacement source={root / 'moved.csv'}",
        "Relink / retry source",
        "missing-ready",
        "Relink / retry source",
        "rejected-ready",
        "Accept changed source content",
        "Relink / retry source",
        "changed-ready",
        "save-ready",
    ]
    owners: list[FileSession] = []
    array_revision: object = None
    started = perf_counter()
    command_started = started

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered, action, array_revision, command_started
        assert "torch" not in sys.modules and "sounddevice" not in sys.modules
        assert editor.playback.snapshot.request is None
        assert not any(
            f.analysis.jobs.results or f.analysis.jobs.busy
            for f in editor.file_sessions
        )
        params = hello_imgui.get_runner_params()
        if stage == 0:
            if editor.workspace_jobs.busy or len(editor.files) != (
                1 if mode == "legacy" else 3
            ):
                return
            owners.extend(editor.file_sessions)
            if mode == "legacy":
                file = editor.active
                if file.loader.active is None:
                    return
                assert file.identity == "legacy-source"
                assert file.loader.active.dataset.table.height == 2
                assert file.loader.active.dataset.source.path == root / "moved.csv"
                params.docking_params.focus_dockable_window("Table preview")
                report["legacy_source"] = True
            else:
                train, test, owner = editor.files
                assert owner.loader.active is not None
                assert len(owner.record_views.files) == 2
                assert all(f.deferred for f in owner.record_views.files)
                assert owner.arrays.store.extractions == 0
                assert all(
                    j.started == 0 and j.active is None
                    for j in (
                        editor.text_comparison_jobs,
                        editor.image_comparison_jobs,
                        editor.audio_comparison_jobs,
                    )
                )
                array_revision = owner.loader.revision
                if mode == "reopened":
                    assert train.loader.active and test.loader.active
                    assert train.loader.active.dataset.table.height == 2
                    assert test.loader.active.dataset.table.height == 4
                    assert train.selection.row_ids == {0}
                    assert test.selection.row_ids == set()
                    report["idle_reopen"] = True
                    editor.activate(train.identity)
                else:
                    assert train.recovery and not train.recovery.changed
                    assert test.recovery and test.recovery.changed
                    report["independent_failures"] = True
                    editor.activate(train.identity)
                params.docking_params.focus_dockable_window("Table preview")
            report["restore_seconds"] = perf_counter() - started
            assert perf_counter() - started < 3
            stage, entered = 1, evidence.frames
            return
        if mode != "recover":
            if evidence.frames - entered > 35:
                assert evidence.max_rendered_rows >= 2
                report["rendered_rows"] = evidence.max_rendered_rows
                params.app_shall_exit = True
                stage = 2
            return
        train, test, owner = editor.files
        assert owner.loader.revision == array_revision
        assert owner.arrays.store.extractions == 0
        target = commands[action] if action < len(commands) else "complete"
        age = evidence.frames - entered
        if age > 250:
            raise AssertionError(
                f"Native recovery stalled: {target}; {editor.workspace_jobs.message}"
            )
        if target.endswith("-ready"):
            if editor.workspace_jobs.busy or age < 12:
                return
            if target == "missing-ready":
                assert train.loader.active and train.recovery is None
                assert train.loader.active.dataset.source.path == root / "moved.csv"
                assert train.loader.active.dataset.table.height == 2
                assert train.selection.row_ids == {0}
                assert test.recovery and test.recovery.changed
                report["missing_relinked"] = True
                editor.activate(test.identity)
                params.docking_params.focus_dockable_window("Table preview")
            elif target == "rejected-ready":
                assert (
                    test.loader.active is None
                    and test.recovery
                    and test.recovery.changed
                )
                assert not test.workspace.accept_changed
                report["changed_requires_consent"] = True
            elif target == "changed-ready":
                assert test.loader.active and test.recovery is None
                assert test.loader.active.dataset.table.height == 4
                assert not test.selection.row_ids
                report["changed_accepted"] = True
                editor.save_workspace(root / "recovered.datelier", overwrite=True)
            elif target == "save-ready":
                assert editor.workspace_jobs.saved is not None
                recipe = (
                    read_session_workspace(root / "recovered.datelier").files[0].recipe
                )
                assert recipe is not None
                save_workspace(root / "legacy.datelier", recipe)
                report["saved_recovery"] = True
            report[target + "_seconds"] = perf_counter() - command_started
            action, entered = action + 1, evidence.frames
            return
        if target == "complete":
            params.app_shall_exit = True
            stage = 2
        elif controls.advance(target, evidence.frames):
            action, entered = action + 1, evidence.frames
            command_started = perf_counter()

    def guarded(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        try:
            frame(editor, tabs, evidence)
        except Exception as error:
            report["failure"] = repr(error)
            report["action"] = (
                commands[action] if action < len(commands) else "complete"
            )
            hello_imgui.get_runner_params().app_shall_exit = True

    with controls.patched(), patch("datelier.gui.app.configure_layout", layout):
        evidence = run_gui(
            initial_workspace=workspace,
            preferences_path=root / f"preferences-{mode}.json",
            smoke_frames=1000,
            on_editor_frame=guarded,
        )
    pixels = hello_imgui.final_app_window_screenshot()
    assert pixels is not None
    Image.fromarray(pixels).save(output / f"{mode}.png")
    assert "failure" not in report and stage == 2, report
    assert all(
        f.closed
        and f.arrays.store.stored_bytes == 0
        and f.images.canvas.retained_bytes == 0
        and f.audio.canvas.retained_bytes == 0
        and f.reference_view.textures.retained_bytes == 0
        for f in owners
    )
    p95 = float(np.percentile(evidence.frame_intervals_ms[10:], 95))
    assert p95 < 33, p95
    report.update(
        frames=evidence.frames,
        frame_p95_ms=p95,
        no_playback_or_training=True,
        closed_array_bytes=0,
        closed_gpu_bytes=0,
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("recover", "reopened", "legacy"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.mode:
        report = run(args.root, args.output, args.mode)
        (args.output / f"{args.mode}.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))
        return
    train, test = args.root / "train.csv", args.root / "test.csv"
    original_train = hashlib.sha256(train.read_bytes()).hexdigest()
    original_test = test.read_bytes()
    train.rename(args.root / "moved.csv")
    test.write_bytes(
        original_test + b"4,changed record,assets/image-0.png,assets/audio-0.wav,9\n"
    )
    sources = tuple(
        p for p in args.root.rglob("*") if p.suffix in (".csv", ".npz", ".wav", ".png")
    )
    hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    try:
        for mode in ("recover", "reopened", "legacy"):
            subprocess.run(
                [
                    sys.executable,
                    __file__,
                    "--root",
                    str(args.root),
                    "--output",
                    str(args.output),
                    "--mode",
                    mode,
                ],
                check=True,
            )
        assert all(
            hashlib.sha256(p.read_bytes()).hexdigest() == value
            for p, value in hashes.items()
        )
    finally:
        test.write_bytes(original_test)
        (args.root / "moved.csv").rename(train)
    assert hashlib.sha256(train.read_bytes()).hexdigest() == original_train
    assert test.read_bytes() == original_test
    (args.output / "source-integrity.json").write_text(
        json.dumps(
            {
                "checked_sources": len(sources),
                "source_bytes_preserved_by_application": True,
                "deliberate_temporary_fixture_changes_restored": True,
                "modes": ["recover", "reopened", "legacy"],
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
