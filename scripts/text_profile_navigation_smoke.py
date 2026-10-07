"""Native Profiles field/type changes and independent-process text restoration."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs


def run(root: Path, output: Path, *, restore: bool) -> dict[str, object]:
    pixels: dict[str, tuple[float, float]] = {}
    original_button, original_checkbox, original_combo = (
        imgui.button,
        imgui.checkbox,
        imgui.combo,
    )
    workspace = root / "session.datelier.json"
    actions = (
        ["Calculate corpus profile", "profile:notes", "save"]
        if restore
        else [
            "selector",
            "text",
            "Done",
            "Calculate corpus profile",
            "profile:text",
            "selector",
            "value",
            "Done",
            "numeric:value",
            "selector",
            "cat",
            "Done",
            "chart",
            "text option",
            "text category",
            "Calculate corpus profile",
            "profile:cat",
            "selector",
            "notes",
            "Done",
            "changed field",
            "Calculate corpus profile",
            "profile:notes",
            "save",
        ]
    )
    action = phase = entered = 0
    started = False
    observed: dict[str, object] = {}

    def capture(label: str) -> None:
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        center = imgui.ImVec2((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)
        if imgui.is_rect_visible(center, imgui.ImVec2(center.x + 1, center.y + 1)):
            pixels[label] = center.x, center.y
        else:
            pixels.pop(label, None)

    def button(label: str, size: imgui.ImVec2 | None = None) -> bool:
        result = original_button(label, size)
        if label.endswith("###Profile columns"):
            capture("selector")
        elif label in ("Done", "Calculate corpus profile"):
            capture(label)
        return result

    def checkbox(label: str, checked: bool) -> tuple[bool, bool]:
        result = original_checkbox(label, checked)
        if label.endswith("##Profile choice"):
            capture(label.removesuffix("##Profile choice"))
        return result

    def combo(label: str, index: int, choices: list[str]) -> tuple[bool, int]:
        result = original_combo(label, index, choices)
        if label == "##Chart type" and choices == ["Counts", "Text tokens"]:
            capture("chart")
            lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
            pixels["text option"] = (
                (lo.x + hi.x) / 2,
                hi.y + imgui.get_frame_height() * 1.5,
            )
        return result

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal action, phase, entered, started
        file = editor.active
        if file.loader.active is None or file.explorer.active is None:
            if restore:
                ready = next((f for f in editor.files if f.loader.active), None)
                if ready:
                    editor.activate(ready.identity)
            return
        view, jobs = file.exploration.profile, file.text.jobs
        if not started:
            started = True
            labels = [
                w.label
                for w in hello_imgui.get_runner_params().docking_params.dockable_windows
            ]
            assert "Text" not in labels and "Explore" in labels
            assert not jobs.busy and jobs.profile is None and jobs.active is None
            if restore:
                assert view.selection.columns == ("notes",) and view.text
                assert jobs.settings.column == "notes"
                assert file.exploration.active_tab == "Profiles"
                observed["restored_selection_without_text_work"] = True
            else:
                assert view.selection.columns == ("value",)
            hello_imgui.get_runner_params().docking_params.focus_dockable_window(
                "Explore"
            )
            entered = evidence.frames
        age = evidence.frames - entered
        if action == len(actions):
            if restore or editor.workspace_jobs.saved is not None:
                hello_imgui.get_runner_params().app_shall_exit = True
            return
        target = actions[action]
        if target.startswith("profile:"):
            column = target.removeprefix("profile:")
            result = jobs.profile
            if result is None or file.text.profiles.shown < 5 or age < 15:
                return
            assert result.profile.settings.column == column
            assert result.profile.documents == 3
            assert result.profile.tokens == {"text": 6, "cat": 3, "notes": 4}[column]
            assert (
                result.profile.vocabulary_size
                == {"text": 5, "cat": 2, "notes": 4}[column]
            )
            assert view.selection.columns == (column,)
            observed[column] = {
                "tokens": result.profile.tokens,
                "types": result.profile.vocabulary_size,
            }
        elif target == "numeric:value":
            group = file.explorer.profiles.active
            if group is None or age < 15:
                return
            assert tuple(p.name for p in group.profiles.columns) == ("value",)
            assert (
                jobs.profile is not None
                and jobs.profile.profile.settings.column == "text"
            )
            observed["numeric_switch"] = True
        elif target in ("text category", "changed field"):
            if age < 8:
                return
            assert not jobs.busy and jobs.profile is None
            assert view.selection.columns == (
                ("cat",) if target == "text category" else ("notes",)
            )
            assert view.text
            assert file.loader.active.dataset.role("cat").role.value == "Categorical"
            observed[target] = True
        elif target == "save":
            if age < 15:
                return
            if not restore:
                # A removed panel's old ini entry must not break the Explore dock.
                layout = imgui.save_ini_settings_to_memory() + (
                    "\n[Window][Text]\nPos=0,0\nSize=300,300\nCollapsed=0\n"
                    f"DockId=0x{file.exploration.dock_id:08X},0\n"
                )
                editor.save_workspace(workspace, layout=layout)
        else:
            io = imgui.get_io()
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
                action, phase, entered = action + 1, 0, evidence.frames
            return
        action, phase, entered = action + 1, 0, evidence.frames

    with (
        patch.object(imgui, "button", new=button),
        patch.object(imgui, "checkbox", new=checkbox),
        patch.object(imgui, "combo", new=combo),
    ):
        evidence = run_gui(
            None if restore else root / "source.csv",
            initial_workspace=workspace if restore else None,
            smoke_frames=1600,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    assert action == len(actions), (action, actions[action:], pixels)
    output.mkdir(parents=True, exist_ok=True)
    screenshot = output / ("profiles-restored.png" if restore else "profiles-text.png")
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        screenshot
    )
    return {
        "frames": evidence.frames,
        "restore": restore,
        "native_actions": True,
        **observed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-profile-navigation")
    )
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, args.output, restore=True)))
        return
    with TemporaryDirectory(prefix="datelier-profile-navigation-") as directory:
        root = Path(directory)
        source = root / "source.csv"
        source.write_text(
            "id,value,cat,text,notes\n"
            "1,1,red,alpha beta beta,one two\n"
            "2,2,red,gamma δ 中,three\n"
            '3,3,blue,"",four\n'
        )
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        first = run(root, args.output, restore=False)
        completed = subprocess.run(
            [
                sys.executable,
                __file__,
                "--restore",
                str(root),
                "--output",
                str(args.output),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        report = {
            "save": first,
            "reopen": json.loads(completed.stdout.strip().splitlines()[-1]),
        }
        assert before == hashlib.sha256(source.read_bytes()).hexdigest()
        report["source_preserved"] = True
        (args.output / "profiles-native.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
