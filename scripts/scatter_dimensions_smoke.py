"""Native 2D/3D choices, nested axes, fixed reduction outputs and saved heights."""

import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from imgui_bundle import hello_imgui, imgui

from datelier.analysis.types import Algorithm, EmbeddingResult
from datelier.gui import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    source = Path("/home/ummdogsss/Downloads/titanic_train.csv")
    before = sha256(source.read_bytes()).hexdigest()
    original = imgui.combo
    fields: dict[str, tuple[float, float]] = {}
    options: dict[str, tuple[float, float]] = {}
    stage, entered, action, phase = 0, 0, 0, 0
    actions = ["##Coordinates", "pca", "run2", "##Chart type", "3d", "run3"]
    labels: set[str] = set()
    observed: dict[str, object] = {}

    def combo(label: str, index: int, choices: list[str]) -> tuple[bool, int]:
        result = original(label, index, choices)
        if imgui.internal.get_current_window().name == "Explore":
            labels.add(label)
            low, high = imgui.get_item_rect_min(), imgui.get_item_rect_max()
            center = ((low.x + high.x) / 2, (low.y + high.y) / 2)
            fields[label] = center
            if label in ("##Coordinates", "##Chart type"):
                options["pca" if label == "##Coordinates" else "3d"] = (
                    center[0],
                    high.y + imgui.get_frame_height() * 1.5,
                )
        return result

    with TemporaryDirectory(prefix="datelier-scatter-dimensions-") as folder:
        preferences = Path(folder) / "preferences.json"

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, entered, action, phase
            if session.explorer.active is None:
                labels.clear()
                return
            plots, analysis, view = session.plots, session.analysis, session.exploration
            io = imgui.get_io()
            age = evidence.frames - entered
            if stage == 0:
                view.tab = "Relationships"
                analysis.controls.features = ["age", "fare", "sibsp", "parch"]
                view.scatter_area.height, view.scatter3d_area.height = 220, 260
                stage, entered = 1, evidence.frames
            elif stage == 1 and age > 15:
                assert {"##Coordinates", "##X", "##Y", "##Colors"} <= labels
                assert fields["##Coordinates"][1] < fields["##X"][1] < fields["##Y"][1]
                assert fields["##X"][0] == fields["##Coordinates"][0]
                assert "##Z" not in labels and "##Dimensions" not in labels
                assert not analysis.jobs.results and not analysis.jobs.busy
                stage, entered = 2, evidence.frames
            elif stage == 2:
                if action == 2 and Algorithm.PCA not in analysis.jobs.results:
                    assert analysis.source == Algorithm.PCA
                    assert analysis.controls.dimensions == 2
                    assert not {"##X", "##Y", "##Z", "##Output dimensions"} & labels
                target = actions[action]
                pixel = (
                    analysis.run_pixel
                    if target.startswith("run")
                    else options[target]
                    if target in options
                    else fields.get(target)
                )
                if phase == 0 and age > 10 and pixel is not None:
                    io.mouse_pos = imgui.ImVec2(*pixel)
                    io.want_set_mouse_pos = True
                    phase, entered = 1, evidence.frames
                elif phase == 1 and age > 3:
                    io.add_mouse_button_event(0, True)
                    phase, entered = 2, evidence.frames
                elif phase == 2 and age > 3:
                    io.add_mouse_button_event(0, False)
                    phase, entered = 3, evidence.frames
                elif phase == 3 and age > 8:
                    if target == "run2":
                        result = analysis.jobs.results.get(Algorithm.PCA)
                        if (
                            not isinstance(result, EmbeddingResult)
                            or analysis.plots.active is None
                        ):
                            return
                        assert result.values.shape[1] == 2
                        assert analysis.plots.active.z is None
                        observed["pca_2d"] = True
                    elif target == "3d":
                        assert plots.chart_choice == "Scatter 3D"
                        assert analysis.controls.dimensions == 3
                        assert view.scatter3d.frames == 0
                        assert not analysis.jobs.busy
                        observed["mismatched_result_not_rendered"] = True
                    elif target == "run3":
                        result = analysis.jobs.results.get(Algorithm.PCA)
                        if (
                            not isinstance(result, EmbeddingResult)
                            or result.values.shape[1] != 3
                        ):
                            return
                        if view.scatter3d.frames < 5:
                            return
                        assert (
                            analysis.plots.active is not None
                            and analysis.plots.active.z is not None
                        )
                        observed["pca_3d"] = True
                    action += 1
                    phase, entered = 0, evidence.frames
                    if action == len(actions):
                        stage = 3
            elif stage == 3 and age > 10:
                assert (
                    view.scatter_area.height == 220
                    and view.scatter3d_area.height == 260
                )
                for algorithm in Algorithm:
                    if not algorithm.is_clustering:
                        assert analysis.controls.request(algorithm).dimensions == 3
                analysis.source = None
                stage, entered = 4, evidence.frames
            elif stage == 4 and age > 15:
                assert {"##Coordinates", "##X", "##Y", "##Z"} <= labels
                assert fields["##Y"][1] < fields["##Z"][1]
                plots.choose_chart("Scatter 2D")
                stage, entered = 5, evidence.frames
            elif stage == 5 and age > 15:
                assert analysis.controls.dimensions == 2 and "##Z" not in labels
                assert (
                    view.scatter_area.height == 220
                    and view.scatter3d_area.height == 260
                )
                observed["nested_raw_axes"] = observed["independent_heights"] = True
                hello_imgui.get_runner_params().app_shall_exit = True
            labels.clear()

        with patch.object(imgui, "combo", side_effect=combo):
            evidence = run_gui(
                source, smoke_frames=2000, on_frame=frame, preferences_path=preferences
            )
        assert stage == 5, (stage, action, phase)
        reopened = False

        def reopen(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal reopened
            if session.explorer.active is None or evidence.frames < 30:
                return
            assert session.plots.chart_choice == "Scatter 2D"
            assert session.analysis.controls.dimensions == 2
            assert session.exploration.scatter_area.height == 220
            assert session.exploration.scatter3d_area.height == 260
            assert not session.analysis.jobs.results and not session.analysis.jobs.busy
            reopened = True
            hello_imgui.get_runner_params().app_shall_exit = True

        run_gui(source, smoke_frames=500, on_frame=reopen, preferences_path=preferences)
        assert reopened and before == sha256(source.read_bytes()).hexdigest()
        print(
            json.dumps(
                {
                    **observed,
                    "frames": evidence.frames,
                    "reopened": True,
                    "source_preserved": True,
                }
            )
        )


if __name__ == "__main__":
    main()
