"""Completion preserves focus; explicit result opening and file tabs navigate."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui

from datelier.analysis.types import Algorithm
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe, ViewScope
from datelier.gui.editor_session import EditorSession
from datelier.inspection.comparison_settings import ComparisonSettings


def main() -> None:
    stage = entered = 0
    with TemporaryDirectory(prefix="datelier-shell-") as directory:
        source = Path(directory) / "source.parquet"
        pl.DataFrame(
            np.random.default_rng(4).normal(size=(64, 3)), schema=["x", "y", "z"]
        ).write_parquet(source)
        original = source.read_bytes()

        def frame(
            editor: EditorSession, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered
            file = editor.active
            active = file.loader.active
            if active is None:
                return
            io = imgui.get_io()
            age = evidence.frames - entered
            if stage == 0 and file.explorer.active is not None:
                file.analysis.controls.features = ["x", "y", "z"]
                file.analysis.controls.start(
                    file.analysis.jobs, active.dataset, Algorithm.PCA
                )
                file.exploration.tab = "Inspect"
                stage, entered = 1, evidence.frames
            elif stage == 1 and file.analysis.pending_result is not None and age > 10:
                assert file.exploration.active_tab == "Inspect"
                assert file.analysis.source is None
                point = probe.point(
                    ViewScope(file.identity, file.identity, active.dataset.revision),
                    "View",
                    "open-result",
                )
                if point is None:
                    return
                io.mouse_pos = imgui.ImVec2(*point)
                io.want_set_mouse_pos = True
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 3, evidence.frames
            elif stage == 3 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 4, evidence.frames
            elif stage == 4 and age > 15:
                assert file.exploration.active_tab == "Relationships"
                assert file.analysis.source == Algorithm.PCA
                assert file.analysis.pending_result is None
                assert file.analysis.plots.active is not None
                editor.comparisons = (ComparisonSettings(),)
                editor.navigation.choose_canvas(True)
                stage, entered = 5, evidence.frames
            elif stage == 5 and age > 10:
                assert editor.navigation.comparing
                second = editor.new_tab(source)
                assert not editor.navigation.comparing
                assert editor.comparisons == (ComparisonSettings(),)
                editor.activate(file.identity)
                assert file.exploration.active_tab == "Relationships"
                editor.close_tab(second.identity)
                assert source.read_bytes() == original
                hello_imgui.get_runner_params().app_shall_exit = True

        evidence = run_gui(source, smoke_frames=600, on_probe_frame=frame)
        assert stage == 5, stage
        print(
            json.dumps(
                dict(
                    frames=evidence.frames,
                    no_focus_theft=True,
                    explicit_open_result=True,
                    file_exits_comparison=True,
                    drafts_preserved=True,
                    source_preserved=True,
                )
            )
        )


if __name__ == "__main__":
    main()
