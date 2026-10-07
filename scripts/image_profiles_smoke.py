"""Native image field/profile commands, diagnostic selection and recipe restoration."""

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.tabs import EditorTabs
from datelier.inspection.images.profile_types import PixelScope
from datelier.inspection.references.types import ReferenceSettings


def run(root: Path, output: Path, restore: bool) -> dict[str, object]:
    pixels: dict[str, tuple[float, float]] = {}
    originals = (
        imgui.button,
        imgui.checkbox,
        imgui.begin_tab_item,
        imgui.combo,
        imgui.selectable,
    )
    action = phase = entered = 0
    started = image_checked = False
    actions = (
        ["Prepare image profile", "Expand", "restored"]
        if restore
        else [
            "Columns",
            "image",
            "Done",
            "Prepare image profile",
            "Dimensions",
            "Colors",
            "Channel family",
            "RGB",
            "Record outcomes",
            "record",
            "Profiles",
            "scope",
            "Profile pixels",
            "Sample",
            "Prepare image profile",
            "scope",
            "Colors",
            "Expand",
            "save",
        ]
    )
    report: dict[str, object] = {}

    def capture(label: str) -> None:
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        pixels[label] = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2

    def button(label: str, size: imgui.ImVec2 | None = None) -> bool:
        result = originals[0](label, size)
        capture("Columns" if "###Profile columns" in label else label)
        return result

    def checkbox(label: str, selected: bool) -> tuple[bool, bool]:
        nonlocal image_checked
        result = originals[1](label, selected)
        if label == "image##Profile choice":
            capture("image")
            image_checked = selected
        return result

    def tab(
        label: str, p_open: bool | None = None, flags: int = 0
    ) -> tuple[bool, bool | None]:
        result = originals[2](label, p_open, flags)
        capture(label)
        return result

    def combo(
        label: str, current: int, items: list[str], popup_max_height_in_items: int = -1
    ) -> tuple[bool, int]:
        result = originals[3](label, current, items, popup_max_height_in_items)
        capture(label)
        if label in ("Channel family", "Profile pixels"):
            lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
            pixels["RGB" if label == "Channel family" else "Sample"] = (
                lo.x + 25,
                hi.y
                + imgui.get_style().frame_padding.y
                + imgui.get_text_line_height() / 2
                + imgui.get_text_line_height_with_spacing(),
            )
        return result

    def selectable(
        label: str,
        selected: bool = False,
        flags: int = 0,
        size: imgui.ImVec2 | None = None,
    ) -> tuple[bool, bool]:
        result = originals[4](label, selected, flags, size)
        if label == "1##Image profile record":
            capture("record")
        return result

    original_header = imgui.collapsing_header

    def header(label: str, flags: int = 0) -> bool:
        result = original_header(label, flags)
        if label == "Image collection scope":
            capture("scope")
        return result

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal started, action, phase, entered
        file = editor.active
        if file.loader.active is None:
            ready = next((f for f in editor.file_sessions if f.loader.active), None)
            if restore and ready:
                editor.activate(ready.identity)
            return
        params, io = hello_imgui.get_runner_params(), imgui.get_io()
        if not started:
            assert (
                not file.images.profile_jobs.busy
                and file.images.profile_jobs.active is None
            )
            if restore:
                assert file.exploration.profile.selection.columns == ("image",)
                assert file.images.settings.profile.pixels == PixelScope.SAMPLE
                assert file.images.settings.profile_view.tab == "Colors"
                assert file.images.settings.profile_view.group_mode == "RGB"
            else:
                file.references.configure(ReferenceSettings(roots=(str(root),)))
                file.images.settings = replace(
                    file.images.settings,
                    profile=replace(
                        file.images.settings.profile, pixel_count=2, bins=4
                    ),
                )
                file.exploration.tab = "Profiles"
            params.docking_params.focus_dockable_window("Explore")
            started, entered = True, evidence.frames
        if action == len(actions):
            if (restore and evidence.frames >= 80) or (
                not restore and editor.workspace_jobs.saved is not None
            ):
                params.app_shall_exit = True
            return
        target, age = actions[action], evidence.frames - entered
        data = file.images.profile_jobs.active
        if target in ("save", "restored"):
            if age < 12 or data is None or file.images.profiles.active_tab != "Colors":
                return
            assert data.sampled_pixels and data.profiled_pixels == 8
            assert (data.ready, data.nulls, data.unresolved, data.failures) == (
                4,
                1,
                1,
                1,
            )
            assert file.images.settings.profile_view.group_mode == "RGB"
            assert file.images.profiles.plot_frames > 0
            report.update(
                profiled_pixels=data.profiled_pixels,
                ready=data.ready,
                nulls=data.nulls,
                unresolved=data.unresolved,
                failures=data.failures,
                sampled=True,
                source_rows=data.records["row_id"].to_list(),
                saved_family=file.images.settings.profile_view.group_mode,
            )
            if target == "save":
                editor.save_workspace(
                    root / "profile.datelier.json",
                    layout=imgui.save_ini_settings_to_memory(),
                )
            action, phase, entered = action + 1, 0, evidence.frames
            return
        if target == "image" and image_checked:
            action, phase, entered = action + 1, 0, evidence.frames
            return
        if target == "Prepare image profile" and file.references.busy:
            return
        if phase == 0 and age > 8 and target in pixels:
            io.mouse_pos = imgui.ImVec2(*pixels[target])
            io.want_set_mouse_pos = True
            phase, entered = 1, evidence.frames
        elif phase == 1 and age > 3:
            io.add_mouse_button_event(0, True)
            phase, entered = 2, evidence.frames
        elif phase == 2 and age > 3:
            io.add_mouse_button_event(0, False)
            phase, entered = 3, evidence.frames
        elif phase == 3 and age > 7:
            if target == "Prepare image profile":
                if data is None:
                    return
                if data.settings.pixels == PixelScope.EXACT:
                    assert data.total_pixels == data.profiled_pixels == 24
                    assert (
                        next(
                            s
                            for s in data.summaries
                            if s.key.mode == "RGB" and s.key.name == "G"
                        ).mean
                        == 20
                    )
                    report["exact_pixels"] = 24
            elif target in ("Dimensions", "Colors", "Record outcomes"):
                assert file.images.profiles.active_tab == target
            elif target == "RGB":
                assert file.images.settings.profile_view.group_mode == "RGB"
            elif target == "record":
                assert file.selection.row_ids == {1}
                assert file.exploration.active_tab == "Inspect"
                assert file.inspect.focused_row == 1
                report["native_linked_record"] = True
            elif target == "Sample":
                assert file.images.settings.profile.pixels == PixelScope.SAMPLE
                assert (
                    file.images.profile_jobs.active is None
                    and not file.images.profile_jobs.busy
                )
            action, phase, entered = action + 1, 0, evidence.frames

    with (
        patch.object(imgui, "button", new=button),
        patch.object(imgui, "checkbox", new=checkbox),
        patch.object(imgui, "begin_tab_item", new=tab),
        patch.object(imgui, "combo", new=combo),
        patch.object(imgui, "selectable", new=selectable),
        patch.object(imgui, "collapsing_header", new=header),
    ):
        evidence = run_gui(
            None if restore else root / "source.csv",
            initial_workspace=root / "profile.datelier.json" if restore else None,
            smoke_frames=900,
            on_editor_frame=frame,
            preferences_path=root / ("restore-prefs.json" if restore else "prefs.json"),
        )
    output.mkdir(parents=True, exist_ok=True)
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / ("image-profile-restored.png" if restore else "image-profile.png")
    )
    assert action == len(actions), (action, actions[action:], pixels)
    p95 = float(np.percentile(evidence.frame_intervals_ms[10:], 95))
    assert p95 < 33
    report.update(frames=evidence.frames, frame_p95_ms=p95, restore=restore)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-image-profiles")
    )
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, args.output, True)))
        return
    with TemporaryDirectory(prefix="datelier-image-profiles-") as directory:
        root = Path(directory)
        Image.new("L", (2, 2), 25).save(root / "a.png")
        Image.new("RGB", (3, 2), (10, 20, 30)).save(root / "b.png")
        Image.new("RGBA", (2, 4), (50, 100, 150, 64)).save(root / "c.png")
        image = Image.fromarray(
            np.array([[-5, 0, 5], [np.nan, np.inf, -np.inf]], dtype=np.float32)
        )
        exif = image.getexif()
        exif[274] = 6
        image.save(root / "oriented.tiff", exif=exif)
        (root / "corrupt.png").write_bytes(b"corrupt")
        (root / "source.csv").write_text(
            "id,image,label\n0,a.png,gray\n1,b.png,rgb\n2,c.png,rgba\n3,oriented.tiff,float\n4,missing.png,missing\n5,corrupt.png,corrupt\n6,,null\n"
        )
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.iterdir()
        }
        first = run(root, args.output, False)
        completed = subprocess.run(
            [
                sys.executable,
                __file__,
                "--restore",
                str(root),
                "--output",
                str(args.output),
            ],
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        assert all(
            hashlib.sha256(path.read_bytes()).hexdigest() == digest
            for path, digest in before.items()
        )
        report = {
            "save": first,
            "reopen": json.loads(completed.stdout.strip().splitlines()[-1]),
            "source_preserved": True,
        }
        (args.output / "image-profiles-native.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))


if __name__ == "__main__":
    main()
