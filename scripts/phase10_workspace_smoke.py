"""Fresh-process native save/restore and changed media-member recovery."""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.core.column_roles import ColumnRole
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.inspection.presentation import NumericScale, TablePresentation
from datelier.inspection.records.types import InspectSettings, RecordMode
from datelier.inspection.references.types import ReferenceMapping
from datelier.io.types import ImportFormat, MediaOptions
from datelier.pipeline.operations import SetColumnRole, Sort


def run_stage(root: Path, mode: str) -> dict[str, object]:
    collection, text, csv, workspace = (
        root / "collection",
        root / "note.txt",
        root / "table.csv",
        root / "session.datelier",
    )
    stage = entered = 0
    first_id = ""
    report: dict[str, object] = {}

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, entered, first_id
        if mode == "save":
            file = editor.active
            if stage == 0 and file.loader.active:
                first_id = file.identity
                file.editor.request(Sort(("member",), True))
                stage = 1
            elif stage == 1 and not file.editor.busy:
                file.editor.request(SetColumnRole("size_bytes", ColumnRole.CATEGORY))
                stage = 2
            elif stage == 2 and not file.editor.busy:
                assert file.loader.active
                file.references.configure(
                    replace(
                        file.references.settings,
                        roots=(str(collection),),
                        thumbnail_size=64,
                        cpu_bytes=2 * 1048576,
                        gpu_bytes=1048576,
                        mappings=(
                            ReferenceMapping(
                                "path",
                                str(collection / "0.png"),
                                str(collection / "3.png"),
                            ),
                        ),
                    )
                )
                file.table.presentation.settings = TablePresentation(
                    scale=NumericScale.CUSTOM, minimum=0, maximum=500, badges=False
                )
                file.inspect.settings = InspectSettings(
                    mode=RecordMode.SELECTION,
                    primary="path",
                    supporting=("member", "size_bytes"),
                    gallery=False,
                )
                file.selection.choose(file.loader.active.dataset.revision, (2,))
                lines = editor.new_tab()
                lines.loader.request(
                    text, MediaOptions(text_lines=True), format=ImportFormat.MEDIA
                )
                editor.new_tab(csv)
                stage = 3
            elif stage == 3 and all(f.loader.active for f in editor.files):
                editor.activate(first_id)
                params = hello_imgui.get_runner_params()
                params.docking_params.dockable_window_of_name(
                    "Analysis"
                ).is_visible = False
                params.docking_params.focus_dockable_window("Inspect")
                stage, entered = 4, evidence.frames
            elif stage == 4 and evidence.frames > entered + 15:
                file = next(f for f in editor.files if f.identity == first_id)
                if (
                    file.inspect.focused_row != 2
                    or file.reference_view.preview_frames == 0
                ):
                    return
                editor.save_workspace(
                    workspace,
                    layout=imgui.save_ini_settings_to_memory(),
                    hidden=("Analysis",),
                )
                (root / "dock.json").write_text(
                    json.dumps({"inspect_dock": file.inspect.dock_id})
                )
                stage = 5
            elif stage == 5 and editor.workspace_jobs.saved:
                report.update(files=3, saved=True)
                stage = 9
                hello_imgui.get_runner_params().app_shall_exit = True
        else:
            if len(editor.files) != 3 or editor.workspace_jobs.busy:
                return
            file = next(f for f in editor.files if f.controls.path == str(collection))
            lines = next(f for f in editor.files if f.controls.path == str(text))
            other = next(f for f in editor.files if f.controls.path == str(csv))
            assert lines.loader.active and other.loader.active
            assert lines.loader.active.dataset.table["text"].to_list() == [
                "first line",
                "second line",
            ]
            assert all(
                not f.analysis.jobs.results and not f.analysis.jobs.busy
                for f in editor.files
            )
            if mode == "recover" and stage == 0:
                if file.recovery is None:
                    return
                report["other_tabs_usable_during_recovery"] = True
                editor.recover_source(file.identity, accept_changed=True)
                stage = 1
                return
            if (
                file.loader.active is None
                or file.recovery is not None
                or file.inspect.focused_row != 2
            ):
                return
            assert file.loader.active.dataset.row_ids.to_list() == [3, 2, 1, 0]
            assert file.selection.row_ids == {2}
            assert (
                file.loader.active.dataset.role("size_bytes").role
                == ColumnRole.CATEGORY
            )
            assert (
                file.references.settings.thumbnail_size == 64
                and len(file.references.settings.mappings) == 1
            )
            assert (
                file.table.presentation.settings.scale == NumericScale.CUSTOM
                and not file.table.presentation.settings.badges
            )
            assert (
                file.inspect.settings.mode == RecordMode.SELECTION
                and not file.inspect.settings.gallery
            )
            assert file.inspect.settings.supporting == ("member", "size_bytes")
            expected = json.loads((root / "dock.json").read_text())["inspect_dock"]
            assert file.inspect.dock_id == expected and expected
            assert (
                not hello_imgui.get_runner_params()
                .docking_params.dockable_window_of_name("Analysis")
                .is_visible
            )
            if mode == "recover":
                row = file.loader.active.dataset.table.filter(
                    file.loader.active.dataset.row_ids == 2
                )
                assert row["member"][0] == "2.png" and row["size_bytes"][0] is None
                resolution, _ = file.references.get("path", str(collection / "2.png"))
                if resolution is None or not resolution.message:
                    return
                report.update(missing_record_identity=True, preview_diagnostic=True)
            elif file.reference_view.preview_frames == 0:
                return
            report.update(files=3, restored_settings=True, layout=True, implicit_ml=0)
            stage = 9
            hello_imgui.get_runner_params().app_shall_exit = True

    evidence = run_gui(
        collection if mode == "save" else None,
        initial_workspace=workspace if mode != "save" else None,
        smoke_frames=1500,
        on_editor_frame=frame,
    )
    assert stage == 9, (mode, stage, report)
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        f"/tmp/datelier-phase10-{mode}.png"
    )
    report.update(mode=mode, frames=evidence.frames)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--mode", choices=("save", "restore", "recover"))
    args = parser.parse_args()
    if args.mode:
        assert args.root
        print(json.dumps(run_stage(args.root, args.mode)))
        return
    reports = []
    with TemporaryDirectory(prefix="datelier-phase10-workspace-") as directory:
        root = Path(directory)
        (root / "collection").mkdir()
        for i in range(4):
            Image.new("RGB", (200, 100), (i * 60, 120, 160)).save(
                root / "collection" / f"{i}.png"
            )
        (root / "note.txt").write_text("first line\nsecond line\n")
        (root / "table.csv").write_text("id,value\n1,1.5\n2,2.5\n")
        original = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
        for mode in ("save", "restore", "recover"):
            if mode == "recover":
                (root / "collection" / "2.png").unlink()
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--root",
                    str(root),
                    "--mode",
                    mode,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
                env=os.environ.copy(),
            )
            if result.returncode:
                raise RuntimeError(f"Native {mode} failed:\n{result.stderr}")
            reports.append(json.loads(result.stdout))
        assert all(
            p.read_bytes() == content for p, content in original.items() if p.exists()
        )
    report = {
        "stages": reports,
        "remaining_sources_preserved": True,
        "temporary_directory_removed": not root.exists(),
    }
    Path("/tmp/datelier-phase10-workspace.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
