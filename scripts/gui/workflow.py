"""Native Sort/Undo/Redo and keyboard source-bound export with overwrite protection."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from scripts.support.input import NativeInput, NativeText


def main() -> None:
    with TemporaryDirectory(prefix="datelier-rebuild-workflow-") as directory:
        root = Path(directory)
        first, second = root / "first###.csv", root / "second.csv"
        first.write_text("x###,y\n3,30\n1,10\n2,20\n")
        second.write_text("x###,y\n999,999\n")
        original = {p: p.read_bytes() for p in (first, second)}
        native, text = NativeInput(), NativeText()
        stage = entered = 0
        first_id = second_id = ""
        done = False

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, first_id, second_id, done
            assert evidence.frames < 900, (stage, [k.path for k in probe.targets])
            if native.advance(evidence.frames) or text.advance(evidence.frames):
                return
            age = evidence.frames - entered
            suffix: tuple[str, ...] | None = None
            if stage == 0 and editor.current.inspection and evidence.frames > 20:
                first_id = editor.active_id
                second_id = editor.new_file(second).identity
                stage, entered = 1, evidence.frames
            elif stage == 1 and editor.current.inspection:
                if editor.active_id != first_id:
                    editor.activate(first_id)
                    entered = evidence.frames
                    return
                if age > 8:
                    suffix = ("canvas", "Transform", "tab")
            elif stage == 2 and age > 3:
                suffix = ("Sort", "columns", "open")
            elif stage == 3 and age > 3:
                suffix = ("columns", "list", "bulk")
            elif stage == 4 and age > 3:
                imgui.get_io().add_key_event(imgui.Key.escape, True)
                stage, entered = 5, evidence.frames
            elif stage == 5:
                imgui.get_io().add_key_event(imgui.Key.escape, False)
                suffix = ("Sort", "apply", "run")
            elif stage == 6 and not editor.current.editor.busy and age > 5:
                active = editor.current.inspection
                assert active and active.dataset.row_ids.to_list() == [1, 2, 0]
                suffix = ("files", "undo")
            elif stage == 7 and not editor.current.editor.busy and age > 5:
                active = editor.current.inspection
                assert active and active.dataset.row_ids.to_list() == [0, 1, 2]
                suffix = ("files", "redo")
            elif stage == 8 and not editor.current.editor.busy and age > 5:
                active = editor.current.inspection
                assert active and active.dataset.row_ids.to_list() == [1, 2, 0]
                suffix = ("menus", "File", "menu")
            elif stage == 9 and age > 3:
                suffix = ("menus", "File", "export", "run")
            elif stage == 10 and age > 3:
                suffix = ("export", "path", "value")
            elif stage == 11:
                text.start(str(first), evidence.frames)
                stage, entered = 12, evidence.frames
            elif stage == 12:
                suffix = ("export", "overwrite", "value")
            elif stage == 13:
                suffix = ("export", "write", "run")
            elif stage == 14 and age > 5 and not editor.current.exporter.busy:
                assert "source" in editor.current.exporter.message.casefold(), (
                    editor.current.exporter.message
                )
                assert first.read_bytes() == original[first]
                suffix = ("export", "path", "value")
            elif stage == 15:
                text.start(str(root / "exported.csv"), evidence.frames)
                stage, entered = 16, evidence.frames
            elif stage == 16:
                # Modal command remains captured to first even if activation changes.
                editor.activate(second_id)
                suffix = ("export", "write", "run")
            elif stage == 17 and (root / "exported.csv").exists():
                exported = pl.read_csv(root / "exported.csv")
                assert exported["x###"].to_list() == [1, 2, 3]
                suffix = ("export", "close-window")
            elif stage == 18 and age > 4:
                assert not any(k.path[:1] == ("export",) for k in probe.targets)
                assert all(p.read_bytes() == raw for p, raw in original.items())
                assert not editor.current.analysis.jobs.results
                assert editor.playback.snapshot.request is None
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix:
                point = native.find(probe, suffix)
                if point:
                    native.click_point(point, evidence.frames)
                    stage, entered = stage + 1, evidence.frames

        evidence = run_gui(first, on_probe_frame=frame)
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_sort_undo_redo": True,
            "native_literal_hash_column_picker": True,
            "native_keyboard_export_path": True,
            "source_overwrite_rejected": True,
            "export_retains_captured_source_after_activation": True,
            "native_titlebar_close": True,
            "source_preserved": True,
            "implicit_ml_playback": 0,
        }
        Path("/tmp/datelier-rebuild-workflow.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
