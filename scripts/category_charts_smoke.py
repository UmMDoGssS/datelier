"""Native count-bar choice, row selection, and conditional Titanic charts."""

import json
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from imgui_bundle import hello_imgui, imgui

from datelier.category_charts import CategoryRepresentation as Mode
from datelier.gui import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    source = Path("/home/ummdogsss/Downloads/titanic_train.csv")
    before = sha256(source.read_bytes()).hexdigest()
    original = imgui.combo
    labels: set[str] = set()
    chart_pixel, count_pixel = (0.0, 0.0), (0.0, 0.0)
    stage, entered = 0, 0
    observed: dict[str, object] = {}

    def record(label: str, index: int, choices: list[str]) -> tuple[bool, int]:
        nonlocal chart_pixel, count_pixel
        result = original(label, index, choices)
        if imgui.internal.get_current_window().name == "Explore":
            labels.add(label)
            if label == "##Chart type" and "Scatter" in choices:
                low, high = imgui.get_item_rect_min(), imgui.get_item_rect_max()
                chart_pixel = ((low.x + high.x) / 2, (low.y + high.y) / 2)
                count_pixel = (chart_pixel[0], high.y + imgui.get_frame_height() * 1.5)
        return result

    def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
        nonlocal stage, entered
        dashboard, active = session.explorer.active, session.loader.active
        if dashboard is None or active is None:
            labels.clear()
            return
        age = evidence.frames - entered
        io = imgui.get_io()
        chart = dashboard.category_chart
        if stage == 0:
            session.exploration.tab = "Relationships"
            session.plots.category_column = "sex"
            stage, entered = 1, evidence.frames
        elif stage == 1 and age > 15:
            assert session.exploration.active_tab == "Relationships"
            io.mouse_pos = imgui.ImVec2(*chart_pixel)
            io.want_set_mouse_pos = True
            stage, entered = 2, evidence.frames
        elif stage == 2 and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = 3, evidence.frames
        elif stage == 3 and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = 4, evidence.frames
        elif stage == 4 and age > 4:
            io.mouse_pos = imgui.ImVec2(*count_pixel)
            io.want_set_mouse_pos = True
            stage, entered = 5, evidence.frames
        elif stage == 5 and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = 6, evidence.frames
        elif stage == 6 and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = 7, evidence.frames
        elif stage == 7 and chart is not None and age > 15:
            assert chart.settings.representation == Mode.COUNTS
            assert chart.labels == ("male", "female") and chart.counts.sum() == 850
            assert (
                not {"##Coordinates", "##Colors", "##X", "##Y", "##Value", "##Group by"}
                & labels
            )
            io.mouse_pos = imgui.ImVec2(*session.exploration.categories.bar_pixel)
            io.want_set_mouse_pos = True
            stage, entered = 8, evidence.frames
        elif stage == 8 and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = 9, evidence.frames
        elif stage == 9 and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = 10, evidence.frames
        elif stage == 10 and age > 10:
            assert chart is not None
            assert session.selection.row_ids == frozenset(chart.row_ids[0][0])
            observed["selected_rows"] = len(session.selection.row_ids)
            session.plots.relationship_chart = Mode.MEAN.value
            session.plots.category_value = "survived"
            session.explorer.request(active.dataset, session.plots.settings())
            stage, entered = 11, evidence.frames
        elif stage == 11 and chart is not None and age > 15:
            assert chart.settings.representation == Mode.MEAN
            assert "##Value" in labels and "##Group by" not in labels
            assert not {"##Coordinates", "##Colors", "##X", "##Y"} & labels
            observed["survival_by_sex"] = dict(
                zip(chart.labels, chart.values[0].tolist(), strict=True)
            )
            session.plots.relationship_chart = Mode.GROUPED.value
            session.plots.category_group = "embarked"
            session.explorer.request(active.dataset, session.plots.settings())
            stage, entered = 12, evidence.frames
        elif stage == 12 and chart is not None and age > 15:
            assert chart.settings.representation == Mode.GROUPED
            assert "##Group by" in labels and "##Value" not in labels
            assert chart.counts.sum() == 850 and "Missing (null)" in chart.groups
            assert not session.analysis.jobs.busy and not session.analysis.jobs.results
            observed.update(
                native_chart_choice=True,
                named_categories=True,
                grouped_missing=True,
                conditional_inputs=True,
                implicit_ml_runs=0,
            )
            io.mouse_pos = imgui.ImVec2(2, 2)
            stage, entered = 13, evidence.frames
        elif stage == 13 and age > 10:
            hello_imgui.get_runner_params().app_shall_exit = True
        labels.clear()

    with patch.object(imgui, "combo", side_effect=record):
        evidence = run_gui(source, smoke_frames=1200, on_frame=frame)
    assert stage == 13 and observed, (stage, chart_pixel, count_pixel)
    assert before == sha256(source.read_bytes()).hexdigest()
    pixels = hello_imgui.final_app_window_screenshot()
    height, width = pixels.shape[:2]
    Path("/tmp/datelier-category-charts.ppm").write_bytes(
        f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
    )
    print(json.dumps({**observed, "frames": evidence.frames, "source_preserved": True}))


if __name__ == "__main__":
    main()
