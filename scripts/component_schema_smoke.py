"""Native schema selection through stable probes, including revision and undo."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui, imgui

from datelier.core.column_roles import ColumnRole
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe, ViewScope
from datelier.gui.editor_session import EditorSession
from datelier.pipeline.editing import HistoryAction


def main() -> None:
    stage, entered = 0, 0
    target = (0.0, 0.0)
    with TemporaryDirectory(prefix="datelier-component-") as directory:
        source = Path(directory) / "data.csv"
        source.write_text("id,label,value\n1,a,4\n2,b,5\n3,a,\n")
        before = source.read_bytes()

        def frame(
            editor: EditorSession, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, target
            file = editor.active
            active = file.loader.active
            if active is None:
                return
            dataset = active.dataset
            age = evidence.frames - entered
            io = imgui.get_io()
            if stage == 0 and file.explorer.active is not None:
                hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                    "Schema and nulls"
                )
                stage, entered = 1, evidence.frames
            elif stage == 1 and age > 10:
                scope = ViewScope(file.identity, file.view_name, dataset.revision)
                point = probe.point(scope, "schema", "roles", "id")
                if point is None:
                    return
                target = point
                io.mouse_pos = imgui.ImVec2(*target)
                io.want_set_mouse_pos = True
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 3, evidence.frames
            elif stage == 3 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 4, evidence.frames
            elif stage == 4 and age > 5:
                # Use native keyboard navigation after opening the popup.
                io.add_key_event(imgui.Key.down_arrow, True)
                stage, entered = 5, evidence.frames
            elif stage == 5 and age > 3:
                io.add_key_event(imgui.Key.down_arrow, False)
                stage, entered = 6, evidence.frames
            elif stage == 6 and age > 3:
                io.add_key_event(imgui.Key.enter, True)
                stage, entered = 7, evidence.frames
            elif stage == 7 and dataset.role("id").override == ColumnRole.NUMERIC:
                io.add_key_event(imgui.Key.enter, False)
                assert "id" in file.analysis.controls.numeric
                file.editor.request(HistoryAction.UNDO)
                stage, entered = 8, evidence.frames
            elif stage == 8 and not file.editor.busy and age > 10:
                assert dataset.role("id").role == ColumnRole.IDENTIFIER
                assert "id" not in file.plots.numeric
                assert dataset.row_ids.to_list() == [0, 1, 2]
                assert dataset.table.rows() == [
                    (1, "a", 4),
                    (2, "b", 5),
                    (3, "a", None),
                ]
                assert not file.analysis.jobs.busy and not file.analysis.jobs.results
                stage = 9
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(source, smoke_frames=500, on_probe_frame=frame)
        assert stage == 9, (stage, target)
        assert source.read_bytes() == before
        report = {
            "frames": evidence.frames,
            "frame_p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_role_override": True,
            "undo": True,
            "source_and_rows_preserved": True,
            "implicit_ml_runs": 0,
        }
        print(json.dumps(report))


if __name__ == "__main__":
    main()
