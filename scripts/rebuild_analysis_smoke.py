"""Native shared-selector/Run/Open-result regression for contextual analysis."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui

from datelier.analysis.types import Algorithm
from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe


def main() -> None:
    with TemporaryDirectory(prefix="datelier-rebuild-analysis-") as directory:
        path = Path(directory) / "source.csv"
        rng = np.random.default_rng(2)
        pl.DataFrame({n: rng.normal(size=120) for n in ("x", "y", "z")}).write_csv(path)
        original = path.read_bytes()
        stage, entered = 0, 0
        clicking: tuple[float, float] | None = None
        next_stage = 0
        click_phase = 0
        completed = False

        def target(probe: GuiProbe, suffix: tuple[str, ...]) -> tuple[float, float]:
            return next(
                value
                for key, value in probe.targets.items()
                if key.path[-len(suffix) :] == suffix
            )

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, clicking, click_phase, next_stage, completed
            file = editor.active
            io = imgui.get_io()
            age = evidence.frames - entered
            if evidence.frames > 1500:
                raise AssertionError((stage, file.analysis.jobs.message))
            if clicking is not None:
                if age < 4:
                    return
                if click_phase == 0:
                    io.add_mouse_button_event(0, True)
                    click_phase, entered = 1, evidence.frames
                elif click_phase == 1:
                    io.add_mouse_button_event(0, False)
                    click_phase, entered = 2, evidence.frames
                else:
                    clicking = None
                    stage, entered = next_stage, evidence.frames
                return
            suffix: tuple[str, ...] | None = None
            if stage == 0 and file.explorer.active and evidence.frames > 20:
                assert not file.analysis.jobs.busy and file.analysis.jobs.latest is None
                suffix, next_stage = ("Relationships", "tab"), 1
            elif stage == 1 and age > 4:
                suffix, next_stage = ("analysis", "features", "open"), 2
            elif stage == 2 and age > 4:
                suffix, next_stage = ("features", "list", "bulk"), 3
            elif stage == 3 and age > 4:
                assert file.analysis.controls.features == ["x", "y", "z"]
                # Click outside the picker, then request explicit analysis.
                suffix, next_stage = ("analysis", "run", "run"), 4
                if imgui.is_popup_open("picker", imgui.PopupFlags_.any_popup_id):
                    io.add_key_event(imgui.Key.escape, True)
                    io.add_key_event(imgui.Key.escape, False)
                    return
            elif stage == 4 and age > 4:
                assert file.analysis.jobs.busy or file.analysis.jobs.latest is not None
                suffix, next_stage = ("Profiles", "tab"), 5
            elif stage == 5:
                assert file.views.tab == "Profiles"
                if file.analysis.pending_result == Algorithm.PCA:
                    assert file.analysis.source is None
                    suffix, next_stage = ("Relationships", "tab"), 6
            elif stage == 6 and age > 4:
                suffix, next_stage = ("analysis", "open-result", "run"), 7
            elif stage == 7 and age > 4 and file.analysis.plots.active:
                assert file.analysis.source == Algorithm.PCA
                assert file.views.tab == "Relationships"
                assert file.analysis.pending_result is None
                assert path.read_bytes() == original
                completed = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix is not None:
                try:
                    clicking = target(probe, suffix)
                except StopIteration:
                    raise AssertionError(
                        (suffix, tuple(k.path for k in probe.targets))
                    ) from None
                io.mouse_pos = imgui.ImVec2(*clicking)
                io.want_set_mouse_pos = True
                click_phase, entered = 0, evidence.frames

        evidence = run_gui(path, on_probe_frame=frame)
        assert completed
        print(
            json.dumps(
                {
                    "frames": evidence.frames,
                    "frame_p95_ms": float(
                        np.percentile(evidence.frame_intervals_ms, 95)
                    ),
                    "native_features_run_open": True,
                    "completion_preserves_focus": True,
                    "source_preserved": True,
                }
            )
        )


if __name__ == "__main__":
    main()
