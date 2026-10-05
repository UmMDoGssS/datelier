"""Native pair-grid diagonal choice, all five plots and workspace reopen."""

import argparse
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from imgui_bundle import hello_imgui, imgui

from datelier.gui.app import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("/home/ummdogsss/Downloads/titanic_train.csv"),
    )
    source = parser.parse_args().source
    before = sha256(source.read_bytes()).hexdigest()
    original = imgui.combo
    labels: set[str] = set()
    diagonal_pixel, kde_pixel = (0.0, 0.0), (0.0, 0.0)
    stage, entered = 0, 0
    observed_modes: set[int] = set()

    def record(label: str, index: int, choices: list[str]) -> tuple[bool, int]:
        nonlocal diagonal_pixel, kde_pixel
        result = original(label, index, choices)
        if imgui.internal.get_current_window().name == "Explore":
            labels.add(label)
            if label == "##Diagonal":
                assert choices == ["Histogram", "KDE", "ECDF", "Box", "Violin"]
                low, high = imgui.get_item_rect_min(), imgui.get_item_rect_max()
                diagonal_pixel = ((low.x + high.x) / 2, (low.y + high.y) / 2)
                kde_pixel = (diagonal_pixel[0], high.y + imgui.get_frame_height() * 1.5)
        return result

    with TemporaryDirectory(prefix="datelier-diagonals-") as folder:
        workspace = Path(folder) / "diagonals.datelier"

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, entered
            dashboard, active = session.explorer.active, session.loader.active
            if dashboard is None or active is None:
                labels.clear()
                return
            age = evidence.frames - entered
            view = session.exploration.relationships
            data = dashboard.relationships
            assert data is not None
            io = imgui.get_io()
            if stage == 0:
                session.plots.relationship_features = ["age", "fare", "sibsp"]
                session.exploration.tab = "Correlations"
                view.mode = 1
                session.explorer.request(active.dataset, session.plots.settings())
                stage, entered = 1, evidence.frames
            elif stage == 1 and age > 15:
                assert "##Diagonal" in labels
                observed_modes.add(0)
                io.mouse_pos = imgui.ImVec2(*diagonal_pixel)
                io.want_set_mouse_pos = True
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 3, evidence.frames
            elif stage == 3 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 4, evidence.frames
            elif stage == 4 and age > 4:
                io.mouse_pos = imgui.ImVec2(*kde_pixel)
                io.want_set_mouse_pos = True
                stage, entered = 5, evidence.frames
            elif stage == 5 and age > 3:
                io.add_mouse_button_event(0, True)
                stage, entered = 6, evidence.frames
            elif stage == 6 and age > 3:
                io.add_mouse_button_event(0, False)
                stage, entered = 7, evidence.frames
            elif stage == 7 and age > 15 and data.diagonal_mode == 1:
                assert session.plots.diagonal_mode == 1
                assert view.frames > 0 and all(
                    d is not None for d in data.diagonal_distributions
                )
                assert any(
                    d is not None and len(d.series[0].kde_y)
                    for d in data.diagonal_distributions
                )
                observed_modes.add(1)
                session.plots.diagonal_mode = 2
                session.explorer.request(active.dataset, session.plots.settings())
                stage, entered = 8, evidence.frames
            elif stage == 8 and age > 15 and data.diagonal_mode == 2:
                assert all(
                    d is not None and d.series[0].ecdf_y[-1] == 1
                    for d in data.diagonal_distributions
                )
                observed_modes.add(2)
                session.plots.diagonal_mode = 3
                session.explorer.request(active.dataset, session.plots.settings())
                stage, entered = 9, evidence.frames
            elif stage == 9 and age > 15 and data.diagonal_mode == 3:
                assert all(
                    d is not None and d.series[0].box is not None
                    for d in data.diagonal_distributions
                )
                observed_modes.add(3)
                session.plots.diagonal_mode = 4
                session.explorer.request(active.dataset, session.plots.settings())
                stage, entered = 10, evidence.frames
            elif stage == 10 and age > 15 and data.diagonal_mode == 4:
                observed_modes.add(4)
                session.selection.choose(active.dataset.revision, (0,))
                view.mode = 0
                stage, entered = 11, evidence.frames
            elif stage == 11 and age > 10:
                assert "##Diagonal" not in labels
                assert view.heatmap.frames > 0
                view.mode = 1
                session.workspace.path = str(workspace)
                session.workspace.save(session)
                stage, entered = 12, evidence.frames
            elif stage == 12 and age > 15 and not session.workspace.jobs.busy:
                assert session.workspace.jobs.saved is not None
                assert (
                    not session.analysis.jobs.busy and not session.analysis.jobs.results
                )
                view.area.expanded = True
                stage, entered = 13, evidence.frames
            elif stage == 13 and age > 10:
                hello_imgui.get_runner_params().app_shall_exit = True
            labels.clear()

        with patch.object(imgui, "combo", side_effect=record):
            first = run_gui(source, smoke_frames=1800, on_frame=frame)
        assert stage == 13 and observed_modes == set(range(5)), (stage, observed_modes)
        pixels = hello_imgui.final_app_window_screenshot()
        height, width = pixels.shape[:2]
        Path("/tmp/datelier-pair-diagonals.ppm").write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        ready = 0

        def reopen(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal ready
            dashboard = session.explorer.active
            if dashboard is None or session.loader.active is None:
                return
            if not ready:
                ready = evidence.frames
            if evidence.frames > ready + 15:
                assert session.exploration.active_tab == "Correlations"
                assert session.exploration.relationships.mode == 1
                assert session.plots.diagonal_mode == 4
                assert (
                    dashboard.relationships is not None
                    and dashboard.relationships.diagonal_mode == 4
                )
                assert (
                    not session.analysis.jobs.busy and not session.analysis.jobs.results
                )
                hello_imgui.get_runner_params().app_shall_exit = True

        second = run_gui(
            initial_workspace=workspace, smoke_frames=1000, on_frame=reopen
        )
        assert second.frames < 1000 and ready
    assert before == sha256(source.read_bytes()).hexdigest()
    print(
        json.dumps(
            {
                "modes": sorted(observed_modes),
                "native_kde_choice": True,
                "heatmap_hides_diagonal": True,
                "workspace_reopened": True,
                "frames": first.frames,
                "reopen_frames": second.frames,
                "implicit_ml_runs": 0,
                "source_preserved": True,
            }
        )
    )


if __name__ == "__main__":
    main()
