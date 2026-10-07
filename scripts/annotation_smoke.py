"""Native explicit source/mapping commands, cross-format geometry and idle reopen."""

import argparse
import hashlib
import json
import subprocess
import sys
from contextlib import ExitStack
from dataclasses import fields, replace
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
from datelier.inspection.annotations.jobs import AnnotationJobs
from datelier.inspection.annotations.overlay import screen_box
from datelier.inspection.annotations.settings import (
    AnnotationSource,
    ImageAssociationMapping,
    ImageMatch,
)
from datelier.inspection.annotations.types import AnnotationClass, AnnotationFormat
from datelier.inspection.references.types import ReferenceSettings
from datelier.pipeline.operations import Sort


def fixtures(root: Path) -> None:
    for folder, orientation in (("a", 1), ("b", 6)):
        directory = root / "images" / folder
        directory.mkdir(parents=True)
        exif = Image.Exif()
        exif[274] = orientation
        Image.new("RGB", (80, 40), (30, 90, 160)).save(
            directory / "scene.png", exif=exif
        )
    (root / "source.csv").write_text(
        "image,label\nimages/a/scene.png,z\nimages/b/scene.png,a\n"
    )
    (root / "scene.xml").write_text(
        "<annotation><filename>scene.png</filename><size><width>80</width>"
        "<height>40</height></size><object><name>person</name><bndbox>"
        "<xmin>21</xmin><ymin>11</ymin><xmax>60</xmax><ymax>30</ymax>"
        "</bndbox></object><object><name>invalid</name><bndbox><xmin>5</xmin>"
        "<ymin>1</ymin><xmax>2</xmax><ymax>4</ymax></bndbox></object></annotation>"
    )
    (root / "labels" / "b").mkdir(parents=True)
    (root / "labels" / "b" / "scene.txt").write_text("0 .5 .5 .5 .5\n")
    (root / "coco.json").write_text(
        json.dumps(
            {
                "images": [
                    {
                        "id": 11,
                        "file_name": "images/b/scene.png",
                        "width": 80,
                        "height": 40,
                    }
                ],
                "categories": [{"id": 7, "name": "person"}],
                "annotations": [
                    {
                        "id": 9,
                        "image_id": 11,
                        "category_id": 7,
                        "bbox": [20, 10, 40, 20],
                        "score": 0.75,
                    }
                ],
            }
        )
    )
    (root / "dataset.yaml").write_text("path: .\nval: images\nnames: [person]\n")


def additional(root: Path) -> tuple[AnnotationSource, ...]:
    return (
        AnnotationSource(
            "yolo",
            str(root / "labels/b/scene.txt"),
            AnnotationFormat.YOLO,
            name="YOLO",
            match=ImageMatch.STEM,
            classes=(AnnotationClass(0, "person"),),
            mappings=(ImageAssociationMapping("scene", 1),),
        ),
        AnnotationSource(
            "coco",
            str(root / "coco.json"),
            AnnotationFormat.COCO,
            name="COCO",
            match=ImageMatch.PATH,
        ),
        AnnotationSource(
            "manifest",
            str(root / "dataset.yaml"),
            AnnotationFormat.ULTRALYTICS,
            name="Manifest",
            match=ImageMatch.PATH,
        ),
    )


def run(
    root: Path, output: Path, restore: bool, overlays: bool = False
) -> dict[str, object]:
    pixels: dict[str, tuple[float, float]] = {}
    originals = {
        name: getattr(imgui, name)
        for name in (
            "button",
            "collapsing_header",
            "tree_node",
            "input_text",
            "input_int",
            "begin_tab_item",
            "selectable",
            "checkbox",
        )
    }

    def capture(label: str, field: bool = False) -> None:
        if not imgui.is_item_visible():
            pixels.pop(label, None)
            return
        lo, hi = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        pixels[label] = (lo.x + 35 if field else (lo.x + hi.x) / 2, (lo.y + hi.y) / 2)

    def wrapper(name: str):
        def wrapped(label, *args, **kwargs):
            result = originals[name](label, *args, **kwargs)
            capture(label, name in ("input_text", "input_int"))
            return result

        return wrapped

    def layout(params, callbacks) -> None:
        configure_layout(params, callbacks)
        params.docking_params.docking_splits = []
        for window in params.docking_params.dockable_windows:
            window.dock_space_name = "MainDockSpace"

    actions = (
        [
            "Detection annotations",
            "Load / associate annotations",
            "ready",
            "Associations",
            "scene.png",
            "save",
        ]
        if restore
        else [
            "Detection annotations",
            "Add annotation source",
            f"Annotation file or folder={root / 'scene.xml'}",
            "Explicit image mappings (0)",
            "Annotation image key=scene.png",
            "Mapped source row=1",
            "Confirm row mapping",
            "Source 1###Annotation source",
            "Load / associate annotations",
            "first ready",
            "Load / associate annotations",
            "ready",
            "Associations",
            "scene.png",
            "save",
        ]
    )
    stage = action = phase = entered = 0
    if overlays:
        if restore:
            actions = [
                "Detection annotations",
                "Load / associate annotations",
                "ready",
                "Prepare annotation profiles",
                "profiles ready",
                "Detection annotations",
                "Fit image",
                "pick",
                "pickctrl",
                "save",
            ]
        else:
            actions = actions[:-1] + [
                "Profiles",
                "Prepare annotation profiles",
                "profiles ready",
                "Sizes",
                "size chart",
                "Quality",
                "Classes",
                "person",
                "Detection annotations",
                "Fit image",
                "Overlay sources and filters",
                "YOLO",
                "COCO",
                "Manifest",
                "Overlay sources and filters",
                "Fit image",
                "pick",
                "zoom",
                "pan",
                "Overlay sources and filters",
                "YOLO",
                "COCO",
                "Overlay sources and filters",
                "Fit image",
                "pickctrl",
                "save",
            ]
    prior_zoom = prior_top = 0.0
    report: dict[str, object] = {}
    context_changes: list[object] = []
    original_bind = AnnotationJobs.bind

    def bind(jobs, *args, **kwargs):
        previous = jobs._context
        original_bind(jobs, *args, **kwargs)
        current = jobs._context
        if previous is not None and current is not None and previous != current:
            context_changes.append(
                {
                    field.name: [
                        str(getattr(previous, field.name)),
                        str(getattr(current, field.name)),
                    ]
                    for field in fields(current)
                    if getattr(previous, field.name) != getattr(current, field.name)
                }
            )

    def frame(
        editor: EditorSession, tabs: EditorTabs, evidence: InspectionEvidence
    ) -> None:
        nonlocal stage, action, phase, entered, prior_zoom, prior_top
        file = editor.active
        if file.loader.active is None:
            ready = next(
                (item for item in editor.file_sessions if item.loader.active), None
            )
            if restore and ready:
                editor.activate(ready.identity)
            return
        params = hello_imgui.get_runner_params()
        if stage == 0:
            if not restore and file.references.settings.roots != (str(root),):
                file.references.configure(ReferenceSettings(roots=(str(root),)))
            if (
                file.references.source != file.loader.active.dataset.source.path
                or file.references.index is None
                or file.references.busy
                or editor.workspace_jobs.busy
            ):
                return
            if restore:
                saved = file.images.settings.annotations
                assert (
                    len(saved.sources) == 4
                    and saved.sources[0].mappings[0].expected_key
                )
                assert (
                    file.images.annotations.active is None
                    and not file.images.annotations.busy
                )
                report["restore_idle"] = True
                if overlays:
                    display = file.images.settings.annotation_view
                    assert (
                        display.tab == "Profiles" and display.profile_tab == "Classes"
                    )
                    assert (
                        display.overlay.sources is not None
                        and "manifest" not in display.overlay.sources
                    )
                    assert file.images.settings.viewport.zoom > 1
                    assert (
                        file.images.annotation_profiles.active is None
                        and not file.images.annotation_profiles.busy
                    )
                    report["overlay_controls_restored"] = True
                stage = 2
            else:
                file.editor.request(Sort(("label",)))
                stage = 1
            entered = evidence.frames
            return
        if stage == 1:
            if file.editor.busy or file.loader.active.dataset.table[
                "label"
            ].to_list() != ["a", "z"]:
                return
            stage = 2
        if stage == 2:
            file.inspect.settings = replace(
                file.inspect.settings, primary="image", gallery=False
            )
            file.exploration.tab = "Inspect"
            params.docking_params.focus_dockable_window("Explore")
            stage, entered = 3, evidence.frames
            return
        if action == len(actions):
            if restore or editor.workspace_jobs.saved is not None:
                params.app_shall_exit = True
            return
        age, target = evidence.frames - entered, actions[action]
        if target == "profiles ready":
            result = file.images.annotation_profiles.active
            if result is None or age < 10:
                return
            assert len(result.sources) == 4
            for profile in result.sources:
                assert len(profile.classes) == 1 and profile.classes[0].count == 1
                assert profile.classes[0].row_ids == (1,)
                assert [summary.mean for summary in profile.summaries] == [
                    40.0,
                    20.0,
                    800.0,
                    2.0,
                ]
            report["known_box_statistics"] = True
            action, phase, entered = action + 1, 0, evidence.frames
            return
        if target == "size chart":
            if file.images.annotation_controls.profiles.plot_frames < 5:
                return
            report["native_size_chart"] = True
            action, phase, entered = action + 1, 0, evidence.frames
            return
        if target in ("pick", "pickctrl", "zoom", "pan"):
            overlay, canvas = file.images.overlay, file.images.canvas
            if not overlay.drawn or age < 10:
                return
            box, (x1, y1, x2, y2) = overlay.drawn[0]
            io = imgui.get_io()
            if phase == 0:
                io.mouse_pos = imgui.ImVec2((x1 + x2) / 2, (y1 + y2) / 2)
                io.want_set_mouse_pos = True
                prior_zoom = file.images.settings.viewport.zoom
                prior_top = file.images.settings.viewport.top
                if target == "pickctrl":
                    io.add_key_event(imgui.Key.left_ctrl, True)
                    io.add_key_event(imgui.Key.mod_ctrl, True)
                phase, entered = 1, evidence.frames
            elif phase == 1 and age > 5:
                if target == "zoom":
                    io.add_mouse_wheel_event(0, 1)
                    phase, entered = 4, evidence.frames
                else:
                    io.add_mouse_button_event(0, True)
                    phase, entered = 2, evidence.frames
            elif phase == 2 and age > 5:
                if target == "pan":
                    mouse = io.mouse_pos
                    io.mouse_pos = imgui.ImVec2(mouse.x - 10, mouse.y - 20)
                    io.want_set_mouse_pos = True
                    phase, entered = 3, evidence.frames
                else:
                    io.add_mouse_button_event(0, False)
                    phase, entered = 4, evidence.frames
            elif phase == 3 and age > 8:
                io.add_mouse_button_event(0, False)
                phase, entered = 4, evidence.frames
            elif phase == 4 and age > 12:
                selected = overlay.selected
                assert canvas.bounds is not None
                for drawn_box, edges in overlay.drawn:
                    assert drawn_box.origin.row_id == 1
                    assert np.allclose(
                        edges,
                        screen_box(
                            drawn_box, file.images.settings.viewport, canvas.bounds[:2]
                        ),
                    )
                report["screen_geometry_aligned"] = True
                if target in ("pick", "pickctrl"):
                    assert selected is not None and selected.origin.row_id == 1, (
                        canvas.clicked,
                        canvas.bounds,
                    )
                    assert selected.source_id == (
                        "yolo"
                        if target == "pickctrl"
                        else file.images.settings.annotations.sources[0].id
                    ), (
                        target,
                        selected.source_id,
                        [box.source_id for box, _ in overlay.drawn],
                        io.key_ctrl,
                        file.images.settings.annotation_view.overlay.sources,
                    )
                    io.add_key_event(imgui.Key.left_ctrl, False)
                    io.add_key_event(imgui.Key.mod_ctrl, False)
                    report["native_overlay_picking"] = True
                elif target == "zoom":
                    assert file.images.settings.viewport.zoom > prior_zoom
                    report["native_overlay_zoom"] = True
                else:
                    assert file.images.settings.viewport.top > prior_top
                    report["native_overlay_pan"] = True
                action, phase, entered = action + 1, 0, evidence.frames
            return
        if target in ("first ready", "ready"):
            prepared = file.images.annotations.active
            if age > 180 and prepared is None and not file.images.annotations.busy:
                raise AssertionError((file.images.annotations.message, context_changes))
            if prepared is None or age < 10:
                return
            if target == "first ready":
                source = prepared.sources[0]
                assert source.images[0].status == "Ready", source.images
                assert (
                    source.recipe.mappings[0].row_id == 1
                    and source.recipe.mappings[0].expected_key
                )
                assert source.boxes[0].box.xyxy == (20, 10, 60, 30)
                file.images.settings = replace(
                    file.images.settings,
                    annotations=replace(
                        file.images.settings.annotations,
                        sources=(
                            *file.images.settings.annotations.sources,
                            *additional(root),
                        ),
                    ),
                )
            else:
                assert len(prepared.sources) == 4
                for source in prepared.sources:
                    assert not source.error and len(source.boxes) == 1, source
                    box = source.boxes[0]
                    assert box.origin.row_id == 1 and box.box.xyxy == (20, 10, 60, 30)
                    assert box.oriented == (10, 20, 30, 60)
                assert prepared.sources[0].issues
                assert any(
                    item.image.label_status == "Missing"
                    for item in prepared.sources[-1].images
                )
                report.update(
                    formats=4,
                    original_xyxy=[20, 10, 60, 30],
                    exif_xyxy=[10, 20, 30, 60],
                    source_row=1,
                    invalid_box_diagnostic=True,
                    missing_label_distinct=True,
                )
            action, phase, entered = action + 1, 0, evidence.frames
            return
        if target == "save":
            if (
                file.inspect.focused_row != 1
                or file.images.canvas.shown < 5
                or age < 15
            ):
                return
            assert file.selection.row_ids == {1}
            if overlays:
                assert (
                    len(file.images.overlay.drawn) == 3
                    and file.images.overlay.selected is not None
                )
                assert file.images.overlay.selected.source_id == "yolo"
                report["multiple_visible_sources"] = 3
            if not restore:
                editor.save_workspace(
                    root / "session.datelier.json",
                    layout=imgui.save_ini_settings_to_memory(),
                )
            report["native_linked_selection"] = True
            action, phase, entered = action + 1, 0, evidence.frames
            return
        key = target.split("=", 1)[0]
        io = imgui.get_io()
        if phase == 0 and age > 8 and key in pixels:
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
                io.add_key_event(imgui.Key.left_ctrl, True)
                io.add_key_event(imgui.Key.mod_ctrl, True)
                io.add_key_event(imgui.Key.a, True)
                phase, entered = 3, evidence.frames
            else:
                phase, entered = 6, evidence.frames
        elif phase == 3 and age > 4:
            io.add_key_event(imgui.Key.a, False)
            io.add_key_event(imgui.Key.left_ctrl, False)
            io.add_key_event(imgui.Key.mod_ctrl, False)
            phase, entered = 4, evidence.frames
        elif phase == 4 and age > 4:
            io.add_input_characters_utf8(target.split("=", 1)[1])
            phase, entered = 5, evidence.frames
        elif phase == 5 and age > 4:
            io.add_key_event(imgui.Key.enter, True)
            phase, entered = 7, evidence.frames
        elif phase == 7 and age > 4:
            io.add_key_event(imgui.Key.enter, False)
            phase, entered = 6, evidence.frames
        elif phase == 6 and age > 8:
            if key == "Annotation file or folder":
                assert file.images.settings.annotations.sources[0].path == str(
                    root / "scene.xml"
                )
            elif key == "Mapped source row":
                controls = next(iter(file.images.annotation_controls.sources.values()))
                assert controls.mapping_row == 1, controls.mapping_row
            action, phase, entered = action + 1, 0, evidence.frames

    with patch("datelier.gui.app.configure_layout", layout):
        with ExitStack() as stack:
            for name in originals:
                stack.enter_context(patch.object(imgui, name, wrapper(name)))
            stack.enter_context(patch.object(AnnotationJobs, "bind", bind))
            evidence = run_gui(
                None if restore else root / "source.csv",
                initial_workspace=root / "session.datelier.json" if restore else None,
                smoke_frames=1800,
                on_editor_frame=frame,
                preferences_path=root
                / ("restore-prefs.json" if restore else "prefs.json"),
            )
    output.mkdir(parents=True, exist_ok=True)
    prefix = "box-overlay" if overlays else "annotations"
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        output / (prefix + ("-restored.png" if restore else ".png"))
    )
    assert action == len(actions), (actions[action:], pixels)
    p95 = float(np.percentile(evidence.frame_intervals_ms[10:], 95))
    assert p95 < 33
    report.update(frames=evidence.frames, frame_p95_ms=p95)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    parser.add_argument("--overlays", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-annotations")
    )
    args = parser.parse_args()
    if args.restore:
        print(json.dumps(run(args.restore, args.output, True, args.overlays)))
        return
    with TemporaryDirectory(prefix="datelier-annotations-") as directory:
        root = Path(directory)
        fixtures(root)
        before = {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*")
            if path.is_file()
        }
        saved = run(root, args.output, False, args.overlays)
        completed = subprocess.run(
            [
                sys.executable,
                __file__,
                "--restore",
                str(root),
                "--output",
                str(args.output),
                *(["--overlays"] if args.overlays else []),
            ],
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        assert all(
            hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
            for path, digest in before.items()
        )
        report = {
            "save": saved,
            "reopen": json.loads(completed.stdout.strip().splitlines()[-1]),
            "sources_preserved": True,
        }
        (
            args.output
            / (
                "box-overlay-native.json"
                if args.overlays
                else "annotations-native.json"
            )
        ).write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
