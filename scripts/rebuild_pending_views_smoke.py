"""Native pending-view closure, completion focus preservation and explicit reopening."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest.mock import patch

import numpy as np
from imgui_bundle import hello_imgui
from rebuild_input import NativeInput

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.table import Inspection
from datelier.io.jobs import loading
from datelier.io.types import ImportFormat, ImportResult, ObjectOptions


def main() -> None:
    with TemporaryDirectory(prefix="datelier-pending-view-") as directory:
        source = Path(directory) / "object.json"
        source.write_text('{"rows":[{"x":3},{"x":1}]}')
        original = source.read_bytes()
        started, release = Event(), Event()
        prepare = loading.prepare_inspection

        def blocked(imported: ImportResult) -> Inspection:
            started.set()
            assert release.wait(5)
            return prepare(imported)

        patcher = patch.object(loading, "prepare_inspection", blocked)
        native = NativeInput()
        stage = entered = 0
        pending_id = ""
        done = patched = False

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, pending_id, done, patched
            owner = editor.active
            age = evidence.frames - entered
            if evidence.frames > 400:
                raise AssertionError((stage, owner.record_views.message))
            if native.advance(evidence.frames):
                return
            suffix: tuple[str, ...] | None = None
            if stage == 0 and evidence.frames > 12:
                owner.open(source, ObjectOptions(), format=ImportFormat.OBJECT)
                stage, entered = 1, evidence.frames
            elif stage == 1 and owner.objects.root and age > 5:
                suffix = ("entries", repr(("rows",)), "open")
            elif stage == 2 and age > 4:
                assert owner.record_views.path == ("rows",)
                patcher.start()
                patched = True
                suffix = ("objects", "records", "run")
            elif stage == 3 and started.is_set():
                pending = editor.current
                assert pending is not owner and pending.inspection is None
                pending_id = pending.identity
                assert pending in owner.record_views.pending
                suffix = ("record-views", "close")
            elif stage == 4 and age > 4:
                assert editor.current is owner and not owner.record_views.pending
                release.set()
                stage, entered = 5, evidence.frames
            elif stage == 5 and not editor.workers.pending:
                assert not owner.record_views.files
                started.clear()
                release.clear()
                suffix = ("objects", "records", "run")
            elif stage == 6 and started.is_set():
                assert (
                    editor.current is not owner
                    and editor.current.identity != pending_id
                )
                owner.record_views.choose(None)
                editor.choose_route("Relationships")
                editor.choose_route("Compare files")
                release.set()
                stage, entered = 7, evidence.frames
            elif stage == 7 and not owner.record_views.pending and age > 5:
                assert editor.current is owner and editor.navigation.comparing
                assert owner.views.tab == "Relationships"
                assert len(owner.record_views.files) == 1
                editor.choose_route("Relationships")
                suffix = ("objects", "records", "run")
            elif stage == 8 and age > 4:
                view = editor.current
                assert view is owner.record_views.files[0] and view.inspection
                assert view.inspection.dataset.table["x"].to_list() == [3, 1]
                assert view.inspection.dataset.row_ids.to_list() == [0, 1]
                assert not owner.record_views.pending
                assert (
                    not view.analysis.jobs.results
                    and not editor.playback.snapshot.request
                )
                assert source.read_bytes() == original
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix:
                point = native.find(probe, suffix)
                if point:
                    native.click_point(point, evidence.frames)
                    stage, entered = stage + 1, evidence.frames

        try:
            evidence = run_gui(on_probe_frame=frame)
        finally:
            release.set()
            if patched:
                patcher.stop()
        assert done
        report = {
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_open_activates_pending_view": True,
            "native_close_pending_view_rejects_late_publication": True,
            "controller_focus_change_preserved_at_completion": True,
            "native_explicit_open_reuses_ready_view": True,
            "source_preserved": True,
            "implicit_analysis_playback": False,
        }
        Path("/tmp/datelier-rebuild-pending-views.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
