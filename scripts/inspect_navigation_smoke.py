"""Native Explore tabs and fresh-process Inspect restoration with an old layout."""

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
    workspace = root / "session.datelier.json"
    pixels: dict[str, tuple[float, float]] = {}
    tab_rows: dict[str, float] = {}
    original_tab, original_checkbox, original_button = (
        imgui.begin_tab_item,
        imgui.checkbox,
        imgui.button,
    )
    actions = (
        ["restored"]
        if restore
        else [
            "Profiles",
            "Relationships",
            "Correlations",
            "Inspect",
            "Gallery",
            "Next record",
            "save",
        ]
    )
    action = phase = entered = 0
    started = False

    def capture(label: str) -> None:
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        pixels[label] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2)

    def tab(
        label: str, p_open: bool | None = None, flags: int = 0
    ) -> tuple[bool, bool | None]:
        result = original_tab(label, p_open, flags)
        if label in ("Profiles", "Relationships", "Correlations", "Inspect"):
            capture(label)
            tab_rows[label] = pixels[label][1]
        return result

    def checkbox(label: str, checked: bool) -> tuple[bool, bool]:
        result = original_checkbox(label, checked)
        if label == "Gallery":
            capture(label)
        return result

    def button(label: str, size: imgui.ImVec2 | None = None) -> bool:
        result = original_button(label, size)
        if label == "Next record":
            capture(label)
        return result

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal action, phase, entered, started
        file = editor.active
        if file.loader.active is None:
            ready = next((f for f in editor.files if f.loader.active), None)
            if restore and ready:
                editor.activate(ready.identity)
            return
        params = hello_imgui.get_runner_params()
        if not started:
            labels = [w.label for w in params.docking_params.dockable_windows]
            assert "Inspect" not in labels and "Explore" in labels
            if restore:
                assert file.exploration.active_tab == "Inspect"
                assert not file.inspect.settings.gallery
                assert file.inspect.settings.focus == 1
                assert not file.text.jobs.busy and file.text.jobs.active is None
            params.docking_params.focus_dockable_window("Explore")
            started, entered = True, evidence.frames
        age = evidence.frames - entered
        if action == len(actions):
            if restore or editor.workspace_jobs.saved is not None:
                params.app_shall_exit = True
            return
        target = actions[action]
        if target in ("save", "restored"):
            if age < 12 or file.inspect.focused_row != 1:
                return
            assert file.exploration.active_tab == "Inspect"
            assert len(tab_rows) == 4 and max(tab_rows.values()) == min(
                tab_rows.values()
            )
            assert file.inspect.dock_id == file.exploration.dock_id != 0
            if not restore:
                layout = imgui.save_ini_settings_to_memory() + (
                    "\n[Window][Inspect]\nPos=0,0\nSize=300,300\nCollapsed=0\n"
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
                if target in tab_rows:
                    assert file.exploration.active_tab == target
                elif target == "Gallery":
                    assert not file.inspect.settings.gallery
                elif target == "Next record":
                    assert file.inspect.settings.focus == 1
                action, phase, entered = action + 1, 0, evidence.frames
            return
        action, phase, entered = action + 1, 0, evidence.frames

    with (
        patch.object(imgui, "begin_tab_item", new=tab),
        patch.object(imgui, "checkbox", new=checkbox),
        patch.object(imgui, "button", new=button),
    ):
        evidence = run_gui(
            None if restore else root / "source.csv",
            initial_workspace=workspace if restore else None,
            smoke_frames=600,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    assert action == len(actions), (action, actions[action:], pixels)
    output.mkdir(parents=True, exist_ok=True)
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / ("inspect-restored.png" if restore else "inspect.png")
    )
    return {"frames": evidence.frames, "same_tab_row": True, "restore": restore}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-inspect-nav")
    )
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, args.output, restore=True)))
        return
    with TemporaryDirectory(prefix="datelier-inspect-nav-") as directory:
        root = Path(directory)
        source = root / "source.csv"
        source.write_text("id,x,y,body\n1,1,2,first\n2,2,4,second\n3,3,6,third\n")
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
        (args.output / "native.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
