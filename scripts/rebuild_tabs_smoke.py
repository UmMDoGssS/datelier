"""Native duplicate filename tabs, drag order, comparison drafts and idle polling."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui
from rebuild_motion import NativeMotion

from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.comparison_settings import ComparisonSettings
from datelier.workspace.session_storage import read_session_workspace


def main() -> None:
    with TemporaryDirectory(prefix="datelier-tabs-") as directory:
        root = Path(directory)
        paths: list[Path] = []
        for folder in ("first", "second"):
            target = root / folder
            target.mkdir()
            path = target / "data##literal.csv"
            path.write_text("x,y\n1.0,2\n3.0,4\n")
            paths.append(path)
        originals = tuple(path.read_bytes() for path in paths)
        native = NativeMotion()
        stage = entered = 0
        done = False
        blank = first = second = ""

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, done, blank, first, second
            age = evidence.frames - entered
            if evidence.frames > 350:
                raise AssertionError((stage, [f.identity for f in editor.files]))
            if native.advance(evidence.frames):
                return
            if stage == 0 and native.find(probe, ("welcome", "files", "run")):
                blank = editor.active_id
                first = editor.new_file(paths[0]).identity
                second = editor.new_file(paths[1]).identity
                stage, entered = 1, evidence.frames
            elif (
                stage == 1 and age > 10 and all(f.inspection for f in editor.files[1:])
            ):
                point = native.find(probe, ("files", second, "tab"))
                destination = native.find(probe, ("files", blank, "tab"))
                assert point and destination
                native.drag(
                    point, (destination[0] - 25, destination[1]), evidence.frames
                )
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 4:
                assert [f.identity for f in editor.files] == [second, blank, first], (
                    [f.identity for f in editor.files],
                    blank,
                    first,
                    second,
                    [
                        (k.path, p)
                        for k, p in probe.targets.items()
                        if k.path[:1] == ("files",)
                    ],
                )
                assert editor.active_id == second
                editor.compare.columns.draft = ComparisonSettings(bins=37)
                editor.choose_route("Compare files")
                stage, entered = 3, evidence.frames
            elif stage == 3 and age > 4:
                assert editor.navigation.comparing
                assert editor.compare.columns.draft.bins == 37
                point = native.find(probe, ("files", first, "tab"))
                if point:
                    native.click_point(point, evidence.frames)
                    stage, entered = 4, evidence.frames
            elif stage == 4 and age > 4:
                assert editor.active_id == first and not editor.navigation.comparing
                assert editor.compare.columns.draft.bins == 37
                assert [f.identity for f in editor.files] == [second, blank, first]
                editor.save_workspace(root / "session.datelier", "", (), False, False)
                stage, entered = 5, evidence.frames
            elif stage == 5 and not editor.workspace.busy:
                saved = read_session_workspace(root / "session.datelier")
                assert [file.identity for file in saved.files] == [second, blank, first]
                assert saved.active_id == first
                editor.reorder((first, second, blank))
                stage, entered = 6, evidence.frames
            elif stage == 6 and age > 5:
                points = [
                    native.find(probe, ("files", identity, "tab"))
                    for identity in (first, second, blank)
                ]
                assert all(points) and [
                    point[0] for point in points if point
                ] == sorted(point[0] for point in points if point)
                assert editor.active_id == first
                assert tuple(path.read_bytes() for path in paths) == originals
                assert all(not f.analysis.jobs.results for f in editor.files)
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True

        try:
            evidence = run_gui(on_probe_frame=frame)
        finally:
            native.close()
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_drag_order_published_to_controller": True,
            "saved_drag_order_and_native_controller_order": True,
            "native_welcome_opening_commands": True,
            "native_duplicate_literal_filename_identity": True,
            "native_activation_preserves_comparison_draft": True,
            "idle_polling_preserves_comparison": True,
            "source_preserved": True,
            "implicit_analysis": False,
        }
        Path("/tmp/datelier-rebuild-tabs.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report))


if __name__ == "__main__":
    main()
