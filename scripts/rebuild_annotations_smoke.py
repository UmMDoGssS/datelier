"""Native association/profile commands, dense cached overlays and scoped picking."""

import json
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui
from PIL import Image
from rebuild_input import NativeInput

from datelier.application.editor import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.annotations.settings import AnnotationSource
from datelier.inspection.annotations.types import AnnotationFormat


def main(distinct: bool = False) -> None:
    with TemporaryDirectory(prefix="datelier-rebuild-annotations-") as directory:
        root = Path(directory)
        source, labels = root / "source.csv", root / "labels.json"
        Image.new("RGB", (128, 96), (12, 24, 36)).save(root / "scene.png")
        source.write_text("image\nscene.png\n")
        labels.write_text(
            json.dumps(
                {
                    "images": [
                        {"id": 1, "file_name": "scene.png", "width": 128, "height": 96}
                    ],
                    "categories": [{"id": 1, "name": "cat"}],
                    "annotations": [
                        {
                            "id": i,
                            "image_id": 1,
                            "category_id": 1,
                            "bbox": [i % 60 * 2, i // 60 * 1.5, 2, 2]
                            if distinct
                            else [5, 5, 40, 40],
                        }
                        for i in range(3000)
                    ],
                }
            )
        )
        originals = (
            source.read_bytes(),
            labels.read_bytes(),
            (root / "scene.png").read_bytes(),
        )
        inputs, stage, entered, done, cached = NativeInput(), 0, 0, False, 0

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, done, cached
            file, tools = editor.current, editor.current.images.annotation_tools
            age = evidence.frames - entered
            if evidence.frames > 500:
                raise AssertionError(
                    (
                        stage,
                        tools.jobs.message,
                        tools.profiles.message,
                        tools.scene.message,
                    )
                )
            if inputs.advance(evidence.frames):
                return
            suffix: tuple[str, ...] | None = None
            if stage == 0 and file.inspection and not file.references.busy:
                file.records.settings = replace(
                    file.records.settings, primary="image", gallery=False
                )
                file.views = replace(file.views, image_height=220)
                editor.choose_route("Inspect")
                tools.apply_source(
                    AnnotationSource(
                        "truth", str(labels), AnnotationFormat.COCO, name="Ground truth"
                    )
                )
                tools.apply_source(
                    AnnotationSource(
                        "pred", str(labels), AnnotationFormat.COCO, name="Prediction"
                    )
                )
                assert tools.jobs.active is None and tools.profiles.active is None
                stage, entered = 1, evidence.frames
            elif stage == 1 and file.images.jobs.active:
                suffix = ("image-settings", "annotations", "toggle")
            elif stage == 2 and age > 5:
                suffix = ("annotation-settings", "associate", "run")
            elif stage == 3 and tools.jobs.active and tools.scene.active:
                scene = tools.scene.active
                assert scene.visible_count == 6000 and len(scene.boxes) == 2000
                assert len(scene.labels) < scene.label_candidates
                item = scene.boxes[0]
                a, b, c, d = item.clipped
                inputs.click_point(((a + c) / 2, (b + d) / 2), evidence.frames)
                stage, entered = 4, evidence.frames
            elif stage == 4 and tools.selected and tools.scene.active:
                assert (
                    file.selection.row_ids == {0} and not file.records.settings.gallery
                )
                cached = tools.scene.prepared_count
                stage, entered = 5, evidence.frames
            elif stage == 5 and age > 25:
                assert tools.scene.prepared_count <= cached + 1
                suffix = ("annotation-settings", "profiles", "toggle")
            elif stage == 6 and age > 5:
                suffix = ("profiles", "prepare", "run")
            elif stage == 7 and tools.profiles.active:
                assert tools.profiles.active.sources[0].classes[0].count == 3000
                suffix = ("annotation-content", "canvas", "Profiles", "tab")
            elif stage == 8 and age > 5:
                if tools.read_view().tab != "Profiles":
                    if inputs.click(
                        probe,
                        ("annotation-content", "canvas", "Profiles", "tab"),
                        evidence.frames,
                    ):
                        entered = evidence.frames
                    return
                suffix = ("annotation-profiles", "canvas", "Sizes", "tab")
            elif stage == 9 and age > 5:
                assert tools.read_view().profile_tab == "Sizes"
                suffix = ("box-size", "expand")
            elif stage == 10 and age > 5:
                suffix = ("box-size", "restore")
            elif stage == 11 and age > 5:
                suffix = ("annotation-profiles", "canvas", "Quality", "tab")
            elif stage == 12 and age > 5:
                suffix = ("annotation-content", "canvas", "Associations", "tab")
            elif stage == 13 and age > 5:
                assert tools.read_view().tab == "Associations"
                assert originals == (
                    source.read_bytes(),
                    labels.read_bytes(),
                    (root / "scene.png").read_bytes(),
                )
                assert file.images.jobs.active and file.images.jobs.active.pixel(
                    0, 0
                ) == (12, 24, 36)
                assert not file.audio.player.snapshot.request
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix and inputs.click(probe, suffix, evidence.frames):
                stage, entered = stage + 1, evidence.frames

        evidence = run_gui(initial_path=source, on_probe_frame=frame)
        assert done
        report = {
            "dense_geometry": "distinct" if distinct else "coincident",
            "frames": evidence.frames,
            "p95_ms": float(np.percentile(evidence.frame_intervals_ms, 95)),
            "native_explicit_association_profiles": True,
            "native_overlay_picking": True,
            "dense_visible_boxes": 6000,
            "bounded_drawn_boxes": 2000,
            "cached_idle_scene": True,
            "dense_label_avoidance": True,
            "native_size_expand_restore": True,
            "native_association_quality_views": True,
            "source_preserved": True,
            "implicit_collection_or_playback": False,
        }
        Path(
            "/tmp/datelier-rebuild-annotations-distinct.json"
            if distinct
            else "/tmp/datelier-rebuild-annotations.json"
        ).write_text(json.dumps(report, indent=2))
        print(json.dumps(report))


if __name__ == "__main__":
    main("--distinct" in sys.argv)
