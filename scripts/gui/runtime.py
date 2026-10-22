"""Exercise production idle pacing, worker wakeup and zero timing retention."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import perf_counter

from imgui_bundle import hello_imgui

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe


def main() -> None:
    started = perf_counter()
    release = Event()
    stage = 0
    done = False

    def blocked() -> None:
        if not release.wait(15):
            raise TimeoutError("Native pacing probe did not release its worker")

    with TemporaryDirectory(prefix="datelier-runtime-") as folder:
        source = Path(folder) / "data.csv"
        source.write_text("x,y\n1,2\n3,4\n")

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, done
            assert perf_counter() - started < 20, stage
            assert not evidence.frame_intervals_ms
            pacing = hello_imgui.get_runner_params().fps_idling
            if stage == 0 and pacing.is_idling:
                assert pacing.enable_idling and editor.workers.pending == 0
                editor.workers.submit(blocked)
                stage = 1
            elif stage == 1:
                assert not pacing.enable_idling
                release.set()
                editor.active.open(source)
                stage = 2
            elif stage == 2 and editor.active.inspection and pacing.is_idling:
                assert pacing.enable_idling and editor.workers.pending == 0
                assert editor.active.inspection.dataset.table.height == 2
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True

        try:
            evidence = run_gui(on_probe_frame=frame, verification=False)
        finally:
            release.set()
        assert done and not evidence.frame_intervals_ms
        assert source.read_text() == "x,y\n1,2\n3,4\n"
    report = {
        "frames": evidence.frames,
        "idle_pacing": True,
        "worker_wakeup_and_publication": True,
        "retained_timing_samples": 0,
    }
    print(json.dumps(report))


if __name__ == "__main__":
    main()
