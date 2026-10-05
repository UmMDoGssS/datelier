"""Exercise a real Schema role override and undo with the Titanic source."""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from imgui_bundle import hello_imgui, imgui

from datelier.core.column_roles import ColumnRole
from datelier.gui import GuiSession, InspectionEvidence, run_gui
from datelier.pipeline.editing import HistoryAction


def main() -> None:
    source = Path("/home/ummdogsss/Downloads/titanic_train.csv")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    combo_pixel = (0.0, 0.0)
    dropdown_pixel = (0.0, 0.0)
    original_combo = imgui.combo
    stage, entered = 0, 0
    observed: dict[str, object] = {}

    def record(label: str, index: int, choices: list[str]) -> tuple[bool, int]:
        nonlocal combo_pixel, dropdown_pixel
        result = original_combo(label, index, choices)
        if label == "##role passenger_id":
            low, high = imgui.get_item_rect_min(), imgui.get_item_rect_max()
            combo_pixel = ((low.x + high.x) / 2, (low.y + high.y) / 2)
            dropdown_pixel = (combo_pixel[0], high.y + imgui.get_frame_height() * 1.5)
        return result

    def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
        nonlocal stage, entered
        active = session.loader.active
        if active is None:
            return
        dataset = active.dataset
        age = evidence.frames - entered
        io = imgui.get_io()
        if stage == 0 and session.explorer.active is not None:
            assert dataset.role("name").distinct == 849
            assert dataset.role("name").role == ColumnRole.CATEGORY
            assert dataset.role("sex").role == ColumnRole.CATEGORY
            assert dataset.role("passenger_id").role == ColumnRole.IDENTIFIER
            assert "passenger_id" not in session.analysis.controls.numeric
            hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                "Schema and nulls"
            )
            stage, entered = 1, evidence.frames
        elif stage == 1 and age > 15:
            io.mouse_pos = imgui.ImVec2(*combo_pixel)
            io.want_set_mouse_pos = True
            stage, entered = 2, evidence.frames
        elif stage == 2 and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = 3, evidence.frames
        elif stage == 3 and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = 4, evidence.frames
        elif stage == 4 and age > 5:
            io.mouse_pos = imgui.ImVec2(*dropdown_pixel)
            io.want_set_mouse_pos = True
            stage, entered = 5, evidence.frames
        elif stage == 5 and age > 3:
            io.add_mouse_button_event(0, True)
            stage, entered = 6, evidence.frames
        elif stage == 6 and age > 3:
            io.add_mouse_button_event(0, False)
            stage, entered = 7, evidence.frames
        elif stage == 7 and dataset.role("passenger_id").override == ColumnRole.NUMERIC:
            assert "passenger_id" in session.analysis.controls.numeric
            session.editor.request(HistoryAction.UNDO)
            stage, entered = 8, evidence.frames
        elif stage == 8 and not session.editor.busy and age > 15:
            assert dataset.role("passenger_id").role == ColumnRole.IDENTIFIER
            assert "passenger_id" not in session.plots.numeric
            assert not session.analysis.jobs.busy and not session.analysis.jobs.results
            observed.update(
                native_override=True,
                undo=True,
                id_excluded=True,
                implicit_ml_runs=0,
            )
            hello_imgui.get_runner_params().app_shall_exit = True

    with patch.object(imgui, "combo", side_effect=record):
        evidence = run_gui(source, smoke_frames=1000, on_frame=frame)
    assert stage == 8 and observed, (stage, combo_pixel, dropdown_pixel)
    assert before == hashlib.sha256(source.read_bytes()).hexdigest()
    pixels = hello_imgui.final_app_window_screenshot()
    height, width = pixels.shape[:2]
    Path("/tmp/datelier-column-roles.ppm").write_bytes(
        f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
    )
    print(json.dumps({**observed, "frames": evidence.frames, "source_preserved": True}))


if __name__ == "__main__":
    main()
