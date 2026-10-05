"""Click real profile checkboxes, render all modes, and reopen saved selections."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from imgui_bundle import hello_imgui, imgui

from datelier.gui import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    source = Path("/home/ummdogsss/Downloads/titanic_train.csv")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    pixels: dict[str, tuple[float, float]] = {}
    original_button, original_checkbox = imgui.button, imgui.checkbox
    actions = [
        ("selector", None),
        ("Clear", ()),
        ("age", ("age",)),
        ("fare", ("age", "fare")),
        ("sex", ("sex",)),
        ("age", ("age",)),
        ("fare", ("age", "fare")),
        ("Done", ("age", "fare")),
    ]
    action, phase, entered = 0, 0, 0
    modes: list[int] = []
    observed: dict[str, object] = {}

    def record(key: str) -> None:
        low, high = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        center = imgui.ImVec2((low.x + high.x) / 2, (low.y + high.y) / 2)
        if imgui.is_rect_visible(center, imgui.ImVec2(center.x + 1, center.y + 1)):
            pixels[key] = (center.x, center.y)
        else:
            pixels.pop(key, None)

    def button(
        label: str,
        size: imgui.ImVec2
        | tuple[float | int, float | int]
        | list[float | int]
        | None = None,
    ) -> bool:
        result = original_button(label, size)
        if label.endswith("##Profile columns"):
            for key in tuple(pixels):
                if key not in ("selector", "Clear", "Done"):
                    pixels.pop(key)
            record("selector")
        elif label in ("Clear", "Done"):
            record(label)
        return result

    def checkbox(label: str, checked: bool) -> tuple[bool, bool]:
        result = original_checkbox(label, checked)
        if label.endswith("##Profile choice"):
            record(label.removesuffix("##Profile choice"))
        return result

    def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
        nonlocal action, phase, entered
        if session.explorer.active is None:
            return
        view = session.exploration.profile
        io = imgui.get_io()
        age = evidence.frames - entered
        if action < len(actions):
            target, expected = actions[action]
            if (
                phase == 0
                and age > 10
                and target in ("sex", "age")
                and target not in pixels
            ):
                anchor = pixels["Clear"]
                io.mouse_pos = imgui.ImVec2(anchor[0], anchor[1] + 100)
                io.want_set_mouse_pos = True
                io.add_mouse_wheel_event(0, -1 if target == "sex" else 1)
                entered = evidence.frames
            if phase == 0 and age > 10 and target in pixels:
                io.mouse_pos = imgui.ImVec2(*pixels[target])
                io.want_set_mouse_pos = True
                phase, entered = 1, evidence.frames
            elif phase == 1 and age > 3:
                io.add_mouse_button_event(0, True)
                phase, entered = 2, evidence.frames
            elif phase == 2 and age > 3:
                io.add_mouse_button_event(0, False)
                phase, entered = 3, evidence.frames
            elif phase == 3 and age > 6:
                if expected is not None:
                    if view.selection.columns != expected:
                        observed["failure"] = str(
                            (target, view.selection.columns, pixels)
                        )
                        hello_imgui.get_runner_params().app_shall_exit = True
                        return
                action += 1
                phase, entered = 0, evidence.frames
            return
        group = session.explorer.profiles.active
        if group is None:
            return
        assert tuple(p.name for p in group.profiles.columns) == ("age", "fare")
        assert group.comparison and len(group.comparison.series) == 2
        assert all(p.statistics for p in group.profiles.columns)
        if age > 15 and len(modes) < 5:
            modes.append(view.mode)
            view.mode = len(modes) if len(modes) < 5 else 0
            entered = evidence.frames
        elif len(modes) == 5 and age > 20:
            view.area.expanded = True
            if age > 35:
                assert (
                    not session.analysis.jobs.busy and not session.analysis.jobs.results
                )
                observed.update(
                    native_checklist=True,
                    exclusive_category=True,
                    modes=modes,
                    selected=view.selection.columns,
                    stats_rows=len(group.profiles.columns),
                )
                hello_imgui.get_runner_params().app_shall_exit = True

    with TemporaryDirectory(prefix="datelier-profile-checklist-") as folder:
        preferences = Path(folder) / "preferences.json"
        with (
            patch.object(imgui, "button", side_effect=button),
            patch.object(imgui, "checkbox", side_effect=checkbox),
        ):
            evidence = run_gui(
                source, smoke_frames=1500, on_frame=frame, preferences_path=preferences
            )
        screenshot = hello_imgui.final_app_window_screenshot()
        height, width = screenshot.shape[:2]
        Path("/tmp/datelier-profile-checklist.ppm").write_bytes(
            f"P6\n{width} {height}\n255\n".encode() + screenshot[:, :, :3].tobytes()
        )
        assert action == len(actions) and modes == list(range(5)) and observed, observed
        reopened = False

        def reopen(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal reopened
            group = session.explorer.profiles.active
            if group is None or evidence.frames < 25:
                return
            assert session.exploration.profile.selection.columns == ("age", "fare")
            assert tuple(p.name for p in group.profiles.columns) == ("age", "fare")
            assert not session.analysis.jobs.busy and not session.analysis.jobs.results
            reopened = True
            hello_imgui.get_runner_params().app_shall_exit = True

        run_gui(source, smoke_frames=800, on_frame=reopen, preferences_path=preferences)
        assert reopened and before == hashlib.sha256(source.read_bytes()).hexdigest()
        print(
            json.dumps(
                {
                    **observed,
                    "frames": evidence.frames,
                    "reopened": reopened,
                    "source_preserved": True,
                    "implicit_ml_runs": 0,
                }
            )
        )


if __name__ == "__main__":
    main()
