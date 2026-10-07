"""Native 2,200-box rendering, visible-limit controls and source preservation."""

import argparse
import hashlib
import json
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
from imgui_bundle import hello_imgui, imgui
from PIL import Image

from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.editor_session import EditorSession
from datelier.gui.layout import configure_layout
from datelier.gui.tabs import EditorTabs
from datelier.inspection.annotations.settings import (
    AnnotationSettings,
    AnnotationSource,
)
from datelier.inspection.annotations.types import AnnotationFormat
from datelier.inspection.images.viewport import ImageViewport
from datelier.inspection.references.types import ReferenceSettings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-overlay-resources")
    )
    args = parser.parse_args()
    with TemporaryDirectory(prefix="datelier-overlay-resource-") as directory:
        root = Path(directory)
        Image.new("RGB", (512, 512), (30, 80, 120)).save(root / "scene.png")
        (root / "source.csv").write_text("image\nscene.png\n")
        (root / "coco.json").write_text(
            json.dumps(
                {
                    "images": [
                        {"id": 1, "file_name": "scene.png", "width": 512, "height": 512}
                    ],
                    "categories": [{"id": 0, "name": "box"}],
                    "annotations": [
                        {
                            "id": index,
                            "image_id": 1,
                            "category_id": 0,
                            "bbox": [(index % 55) * 9, (index // 55) * 9, 7, 7],
                            "score": 0.75,
                        }
                        for index in range(2200)
                    ],
                }
            )
        )
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.iterdir()
        }
        pixels: dict[str, tuple[float, float]] = {}
        expanded: dict[str, bool] = {}
        notices: set[str] = set()
        original_text = imgui.text
        names = ("collapsing_header", "button", "tree_node", "input_int", "checkbox")
        originals = {name: getattr(imgui, name) for name in names}

        def text(value: str, *args) -> None:
            if value.startswith("Showing "):
                notices.add(value)
            original_text(value, *args)

        def wrapper(name: str):
            def wrapped(label, *args, **kwargs):
                result = originals[name](label, *args, **kwargs)
                if name in ("collapsing_header", "tree_node"):
                    expanded[label] = result
                if imgui.is_item_visible():
                    lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
                    pixels[label] = (
                        lo.x + 35 if name == "input_int" else (lo.x + hi.x) / 2,
                        (lo.y + hi.y) / 2,
                    )
                else:
                    pixels.pop(label, None)
                return result

            return wrapped

        def layout(params, callbacks) -> None:
            configure_layout(params, callbacks)
            params.docking_params.docking_splits = []
            for window in params.docking_params.dockable_windows:
                window.dock_space_name = "MainDockSpace"

        actions = [
            "Detection annotations",
            "Load / associate annotations",
            "ready",
            "Detection annotations",
            "limited",
            "Overlay sources and filters",
            "Visible box limit=2200",
            "Overlay sources and filters",
            "all",
            "Overlay sources and filters",
            "Show overlapping box labels",
            "overlap",
            "Show overlapping box labels",
            "Overlay sources and filters",
            "declutter",
        ]
        stage = action = phase = entered = 0
        limited_frames = full_frames = 0
        intervals: list[float] = []

        def frame(
            editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, action, phase, entered, limited_frames, full_frames
            file, params, io = (
                editor.active,
                hello_imgui.get_runner_params(),
                imgui.get_io(),
            )
            active = file.loader.active
            if active is None:
                return
            if stage == 0:
                file.references.configure(ReferenceSettings(roots=(str(root),)))
                file.images.settings = replace(
                    file.images.settings,
                    viewport=ImageViewport(0.25),
                    annotations=AnnotationSettings(
                        "image",
                        (
                            AnnotationSource(
                                "coco", str(root / "coco.json"), AnnotationFormat.COCO
                            ),
                        ),
                    ),
                )
                file.inspect.settings = replace(
                    file.inspect.settings, primary="image", gallery=False
                )
                file.exploration.tab = "Inspect"
                params.docking_params.focus_dockable_window("Explore")
                stage, entered = 1, evidence.frames
            if action == len(actions):
                params.app_shall_exit = True
                return
            target, age = actions[action], evidence.frames - entered
            if action == 0 and file.images.canvas.shown < 12:
                return
            if target in ("overlap", "declutter"):
                overlay = file.images.overlay
                if age < 12 or not overlay.label_candidates:
                    return
                if target == "overlap":
                    assert overlay.labels_shown == overlay.label_candidates
                else:
                    assert overlay.visible_count == len(overlay.drawn) == 2200
                    assert 0 < overlay.labels_shown < overlay.label_candidates
                    assert overlay.scenes_prepared < evidence.frames // 4
                action, phase, entered = action + 1, 0, evidence.frames
                return
            if target == "ready":
                prepared = file.images.annotations.active
                if prepared is None or age < 8:
                    return
                assert len(prepared.sources[0].boxes) == 2200
                action, phase, entered = action + 1, 0, evidence.frames
                return
            if target in ("limited", "all"):
                overlay = file.images.overlay
                wanted = 2000 if target == "limited" else 2200
                if (
                    overlay.visible_count != 2200
                    or len(overlay.drawn) != wanted
                    or age < 10
                ):
                    return
                assert file.images.canvas.retained_bytes <= 512 * 512 * 4
                assert 0 < overlay.labels_shown < overlay.label_candidates
                if target == "limited":
                    limited_frames += 1
                    done = limited_frames >= 120
                else:
                    full_frames += 1
                    done = full_frames >= 120
                intervals.append(evidence.frame_intervals_ms[-1])
                if done:
                    action, phase, entered = action + 1, 0, evidence.frames
                return
            key = target.split("=", 1)[0]
            if phase == 0 and age > 8:
                params.docking_params.focus_dockable_window("Explore")
                phase, entered = 8, evidence.frames
            elif phase == 8 and age > 4 and key in pixels:
                io.mouse_pos = imgui.ImVec2(*pixels[key])
                io.want_set_mouse_pos = True
                phase, entered = 1, evidence.frames
            elif phase == 1 and age > 4:
                io.add_mouse_button_event(0, True)
                phase, entered = 2, evidence.frames
            elif phase == 2 and age > 4:
                io.add_mouse_button_event(0, False)
                if "=" in target:
                    for keycode in (
                        imgui.Key.left_ctrl,
                        imgui.Key.mod_ctrl,
                        imgui.Key.a,
                    ):
                        io.add_key_event(keycode, True)
                    phase = 3
                else:
                    phase = 6
                entered = evidence.frames
            elif phase == 3 and age > 4:
                for keycode in (imgui.Key.a, imgui.Key.left_ctrl, imgui.Key.mod_ctrl):
                    io.add_key_event(keycode, False)
                phase, entered = 4, evidence.frames
            elif phase == 4 and age > 4:
                io.add_input_characters_utf8("2200")
                phase, entered = 5, evidence.frames
            elif phase == 5 and age > 4:
                io.add_key_event(imgui.Key.enter, True)
                phase, entered = 7, evidence.frames
            elif phase == 7 and age > 4:
                io.add_key_event(imgui.Key.enter, False)
                phase, entered = 6, evidence.frames
            elif phase == 6 and age > 8:
                wanted = (
                    action == 0
                    if key == "Detection annotations"
                    else action in (5, 9)
                    if key == "Overlay sources and filters"
                    else None
                )
                if wanted is not None and expanded.get(key) != wanted:
                    phase, entered = 0, evidence.frames
                    return
                if key == "Visible box limit":
                    assert file.images.settings.annotation_view.overlay.limit == 2200
                action, phase, entered = action + 1, 0, evidence.frames

        with patch("datelier.gui.app.configure_layout", layout), ExitStack() as stack:
            for name in names:
                stack.enter_context(patch.object(imgui, name, wrapper(name)))
            stack.enter_context(patch.object(imgui, "text", text))
            evidence = run_gui(
                root / "source.csv",
                smoke_frames=1100,
                on_editor_frame=frame,
                preferences_path=root / "prefs.json",
            )
        assert action == len(actions), (actions[action], phase, list(pixels))
        assert any("2,000/2,200" in value for value in notices)
        assert all(
            hashlib.sha256(path.read_bytes()).hexdigest() == digest
            for path, digest in before.items()
        )
        p95 = float(np.percentile(intervals, 95))
        args.output.mkdir(parents=True, exist_ok=True)
        Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
            args.output / "box-overlay-large.png"
        )
        report = {
            "boxes": 2200,
            "default_limit": 2000,
            "native_raised_limit": 2200,
            "limited_frames": limited_frames,
            "full_frames": full_frames,
            "measured_frame_p95_ms": p95,
            "frames": evidence.frames,
            "class_and_score_labels": True,
            "overlap_avoidance": True,
            "native_overlap_choice": True,
            "cached_scene_invalidation": True,
            "truncation_notice": True,
            "source_preserved": True,
            "gpu_bytes_bound": 512 * 512 * 4,
        }
        (args.output / "box-overlay-large-native.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report))
        assert p95 < 33, p95


if __name__ == "__main__":
    main()
