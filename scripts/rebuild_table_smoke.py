"""Native table styles, shared preview budget, ambiguity mapping and restoration."""

import argparse
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui, imgui
from PIL import Image
from rebuild_input import NativeInput, NativeText

from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.presentation import NumericScale
from datelier.pipeline.operations import Sort


def run(root: Path, restore: bool = False) -> dict[str, object]:
    source, workspace = root / "table.csv", root / "session.json"
    original = source.read_bytes()
    native, text = NativeInput(), NativeText()
    stage = entered = 0
    configured = done = False
    max_gpu = max_uploads = 0.0

    def frame(
        editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered, configured, done, max_gpu, max_uploads
        file = editor.current
        age = evidence.frames - entered
        metrics = next(
            (
                v
                for k, v in probe.measurements.items()
                if k.path[-2:] == ("table", "preview-cache")
            ),
            (0.0, 0.0),
        )
        max_gpu, max_uploads = max(max_gpu, metrics[0]), max(max_uploads, metrics[1])
        assert metrics[0] <= file.references.settings.gpu_bytes and metrics[1] <= 4
        if evidence.frames > 1100:
            raise AssertionError(
                (stage, file.references.message, [k.path for k in probe.targets])
            )
        if restore:
            if (
                not editor.workspace.busy
                and file.inspection
                and metrics[0] > 0
                and evidence.frames > 30
                and any(
                    v[0] > 0
                    for k, v in probe.measurements.items()
                    if k.path[-2:] == ("reference", "excerpt")
                )
            ):
                assert file.table.presentation.settings.scale == NumericScale.CUSTOM
                assert (
                    file.table.presentation.minimum,
                    file.table.presentation.maximum,
                ) == (1.5, 2.5)
                assert not file.table.presentation.settings.badges
                assert file.references.settings.mappings[0].path == str(
                    root / "a" / "pic.png"
                )
                assert file.selection.row_ids == {2}
                assert (
                    not file.analysis.jobs.results
                    and file.audio.player.snapshot.request is None
                )
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            return
        if not configured:
            file.references.configure(
                replace(
                    file.references.settings,
                    roots=(str(root),),
                    cpu_bytes=1048576,
                    gpu_bytes=1048576,
                )
            )
            configured = True
        if native.advance(evidence.frames) or text.advance(evidence.frames):
            return
        suffix = None
        popup = False
        if stage == 0 and file.inspection and file.explorer.active:
            file.editor.request(Sort(("x",), True))
            stage, entered = 1, evidence.frames
        elif stage == 1 and not file.editor.busy:
            resolution, _ = file.references.get("image", "pic.png")
            if resolution and len(resolution.candidates) == 2:
                suffix = ("rows", "0", "1", "reference", "choose")
        elif stage == 2:
            suffix, popup = ("mapping-popup", "candidates", "0", "choose"), True
        elif stage == 3 and metrics[0] > 0:
            assert file.references.settings.mappings[0].path == str(
                root / "a" / "pic.png"
            )
            suffix = ("rows", "0", "source", "select")
        elif stage == 4 and age > 3:
            assert file.selection.row_ids == {2}
            suffix = ("options", "open")
        elif stage == 5:
            suffix, popup = ("presentation", "badges", "value"), True
        elif stage == 6:
            assert not file.table.presentation.settings.badges
            suffix, popup = ("presentation", "scale", "value"), True
        elif stage == 7 and age > 2:
            imgui.get_io().add_key_event(imgui.Key.end, True)
            stage, entered = 8, evidence.frames
        elif stage == 8 and age > 2:
            imgui.get_io().add_key_event(imgui.Key.end, False)
            imgui.get_io().add_key_event(imgui.Key.enter, True)
            stage, entered = 9, evidence.frames
        elif stage == 9 and age > 2:
            imgui.get_io().add_key_event(imgui.Key.enter, False)
            stage, entered = 10, evidence.frames
        elif stage == 10:
            assert file.table.presentation.settings.scale == NumericScale.CUSTOM
            suffix, popup = ("custom", "minimum", "value"), True
        elif stage == 11:
            text.start("1.5", evidence.frames)
            stage, entered = 12, evidence.frames
        elif stage == 12:
            suffix, popup = ("custom", "maximum", "value"), True
        elif stage == 13:
            text.start("2.5", evidence.frames)
            stage, entered = 14, evidence.frames
        elif stage == 14:
            suffix, popup = ("custom", "apply", "run"), True
        elif stage == 15 and age > 3:
            assert (
                file.table.presentation.settings.minimum,
                file.table.presentation.settings.maximum,
            ) == (1.5, 2.5)
            imgui.get_io().add_key_event(imgui.Key.escape, True)
            stage, entered = 16, evidence.frames
        elif stage == 16 and age > 2:
            imgui.get_io().add_key_event(imgui.Key.escape, False)
            file.records.settings = replace(
                file.records.settings, primary="note", gallery=True
            )
            editor.choose_route("Inspect")
            stage, entered = 17, evidence.frames
        elif stage == 17 and file.records.jobs.active and age > 5:
            # Gallery and table share the same GPU accounting/upload limit.
            excerpts = [
                v
                for k, v in probe.measurements.items()
                if k.path[-2:] == ("reference", "excerpt")
            ]
            if excerpts:
                assert excerpts[0][0] == 256
                editor.save_workspace(workspace, "", (), False, False)
                stage, entered = 18, evidence.frames
        elif stage == 18 and not editor.workspace.busy:
            assert editor.workspace.saved is not None, editor.workspace.message
            assert file.inspection and file.inspection.dataset.table[
                "image"
            ].to_list() == ["pic.png", "extra1.png", "extra0.png"]
            assert source.read_bytes() == original and not file.analysis.jobs.results
            done = True
            hello_imgui.get_runner_params().app_shall_exit = True
        if suffix:
            point = native.find(probe, suffix)
            if popup and point:
                native.click_point(point, evidence.frames)
                stage, entered = stage + 1, evidence.frames
            elif not popup and native.click(probe, suffix, evidence.frames):
                stage, entered = stage + 1, evidence.frames

    evidence = run_gui(
        None if restore else source,
        initial_workspace=workspace if restore else None,
        on_probe_frame=frame,
    )
    assert done and source.read_bytes() == original
    report: dict[str, object] = {
        "mode": "restore" if restore else "save",
        "frames": evidence.frames,
        "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
        "native_ambiguous_reference_choice": True,
        "native_custom_shading_and_badges": True,
        "native_original_sorted_row_selection": True,
        "shared_preview_gpu_bytes_max": max_gpu,
        "shared_uploads_per_frame_max": max_uploads,
        "bounded_gallery_text_excerpt": True,
        "source_preserved": True,
        "implicit_analysis_playback": False,
    }
    print(json.dumps(report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    args = parser.parse_args()
    if args.restore:
        report = run(args.restore, True)
        (args.restore / "restore.json").write_text(json.dumps(report))
        return
    with TemporaryDirectory(prefix="datelier-table-") as directory:
        root = Path(directory)
        (root / "table.csv").write_text(
            "x,image,note\n1.0,extra0.png,note.txt\n2.0,extra1.png,note.txt\n3.0,pic.png,note.txt\n"
        )
        (root / "note.txt").write_text("中文 preview " * 100)
        for name, color in (("extra0.png", (0, 255, 0)), ("extra1.png", (255, 255, 0))):
            Image.new("RGB", (32, 24), color).save(root / name)
        for folder, color in (("a", (255, 0, 0)), ("b", (0, 0, 255))):
            (root / folder).mkdir()
            Image.new("RGB", (32, 24), color).save(root / folder / "pic.png")
        saved = run(root)
        subprocess.run([sys.executable, __file__, "--restore", str(root)], check=True)
        restored = json.loads((root / "restore.json").read_text())
        Path("/tmp/datelier-rebuild-table.json").write_text(
            json.dumps({"save": saved, "restore": restored}, indent=2)
        )


if __name__ == "__main__":
    main()
