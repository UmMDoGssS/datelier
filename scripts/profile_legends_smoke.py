"""Native profile legends for every mode, coupled outliers, and single columns."""

import json
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from imgui_bundle import hello_imgui, imgui, implot

from datelier.gui import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    source = Path("/home/ummdogsss/Downloads/titanic_train.csv")
    before = sha256(source.read_bytes()).hexdigest()
    original = implot.end_plot
    labels: tuple[str, ...] = ()
    pixel = (0.0, 0.0)
    hidden, outliers_hidden = False, False
    stage, entered, phase = 0, 0, 0
    modes: list[int] = []

    def end_plot() -> None:
        nonlocal labels, pixel, hidden, outliers_hidden
        plot = implot.internal.get_current_plot()
        # Resolve the outlier item while its plot scope is active.
        outliers = implot.internal.get_item("age outliers")
        original()
        items = plot.items
        current = tuple(
            items.get_legend_label(i) for i in range(items.get_legend_count())
        )
        if "age" in current:
            labels = current
            hidden = not items.get_legend_item(0).show
            outliers_hidden = outliers is not None and not outliers.show
            rect = items.legend.rect_clamped
            pixel = (rect.min.x + 12, rect.min.y + 12)

    def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
        nonlocal stage, entered, phase
        if session.explorer.active is None:
            return
        view = session.exploration.profile
        group = session.explorer.profiles.active
        age = evidence.frames - entered
        io = imgui.get_io()
        if stage == 0:
            view.selection.columns = ("age", "fare")
            view.area.expanded = True
            stage, entered = 1, evidence.frames
        elif stage == 1 and group is not None and age > 15:
            assert labels == ("age", "fare"), labels
            modes.append(view.mode)
            if view.mode == 3:
                assert group.comparison is not None
                assert len(group.comparison.series[0].outliers)
                stage, entered = 2, evidence.frames
            else:
                view.mode += 1
                entered = evidence.frames
        elif stage in (2, 3):
            if phase == 0 and age > 10:
                io.mouse_pos = imgui.ImVec2(*pixel)
                io.want_set_mouse_pos = True
                phase, entered = 1, evidence.frames
            elif phase == 1 and age > 3:
                io.add_mouse_button_event(0, True)
                phase, entered = 2, evidence.frames
            elif phase == 2 and age > 3:
                io.add_mouse_button_event(0, False)
                phase, entered = 3, evidence.frames
            elif phase == 3 and age > 10:
                assert hidden == outliers_hidden == (stage == 2)
                if stage == 2:
                    stage, entered, phase = 3, evidence.frames, 0
                else:
                    view.mode = 4
                    stage, entered = 4, evidence.frames
        elif stage == 4 and age > 15:
            assert labels == ("age", "fare")
            modes.append(4)
            view.selection.columns = ("age",)
            stage, entered = 5, evidence.frames
        elif (
            stage == 5
            and age > 15
            and group is not None
            and len(group.profiles.columns) == 1
        ):
            assert labels == ("age",)
            assert not hidden
            assert not session.analysis.jobs.busy and not session.analysis.jobs.results
            hello_imgui.get_runner_params().app_shall_exit = True

    with patch.object(implot, "end_plot", end_plot):
        evidence = run_gui(source, smoke_frames=1500, on_frame=frame)
    assert stage == 5 and modes == list(range(5))
    assert before == sha256(source.read_bytes()).hexdigest()
    print(
        json.dumps(
            {
                "frames": evidence.frames,
                "profile_modes": modes,
                "native_hide_restore": True,
                "outliers_follow_legend": True,
                "single_column_legend": True,
                "source_preserved": True,
                "implicit_ml_runs": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
