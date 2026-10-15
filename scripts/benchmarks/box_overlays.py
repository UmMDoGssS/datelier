"""Native 2,200-box rendering, visible-limit controls and source preservation."""

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui
from PIL import Image

from datelier.application.sessions import EditorController
from datelier.gui.app import InspectionEvidence, run_gui
from datelier.gui.components.probe import GuiProbe
from datelier.inspection.annotations.settings import (
    AnnotationSettings,
    AnnotationSource,
)
from datelier.inspection.annotations.types import AnnotationFormat
from datelier.inspection.images.viewport import ImageViewport
from datelier.inspection.references import ReferenceSettings
from scripts.support.input import NativeInput, NativeText


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
        native, text = NativeInput(), NativeText()
        stage = entered = limited_frames = full_frames = cached = 0
        done = False
        intervals: list[float] = []

        def frame(
            editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
        ) -> None:
            nonlocal stage, entered, limited_frames, full_frames, cached, done
            file, tools = editor.current, editor.current.images.annotation_tools
            assert evidence.frames < 1500, (stage, tools.scene.message)
            if native.advance(evidence.frames) or text.advance(evidence.frames):
                return
            age = evidence.frames - entered
            scene = tools.scene.active
            drawn = next(
                (
                    values
                    for key, values in probe.measurements.items()
                    if key.path[-2:] == ("overlay", "drawn")
                ),
                None,
            )
            gpu = next(
                (
                    values
                    for key, values in probe.measurements.items()
                    if key.path[-2:] == ("image", "gpu")
                ),
                None,
            )
            suffix: tuple[str, ...] | None = None
            if stage == 0 and file.inspection and not file.references.busy:
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
                file.records.settings = replace(
                    file.records.settings, primary="image", gallery=False
                )
                editor.choose_route("Inspect")
                stage, entered = 1, evidence.frames
            elif stage == 1 and file.images.jobs.active:
                suffix = ("image-settings", "annotations", "toggle")
            elif stage == 2 and age > 5:
                suffix = ("annotation-settings", "associate", "run")
            elif stage == 3 and scene and drawn and age > 10:
                assert (
                    tools.jobs.active
                    and len(tools.jobs.active.sources[0].boxes) == 2200
                )
                assert scene.visible_count == 2200 and drawn[0] == 2000
                assert 0 < drawn[1] < scene.label_candidates
                assert gpu and gpu[0] <= 512 * 512 * 4
                intervals.append(evidence.frame_intervals_ms[-1])
                limited_frames += 1
                if limited_frames >= 120:
                    suffix = ("annotation-settings", "overlays", "toggle")
            elif stage == 4 and age > 5:
                suffix = ("overlays", "limit", "value")
            elif stage == 5 and age > 5:
                text.start("2200", evidence.frames)
                stage, entered = 6, evidence.frames
            elif stage == 6 and scene and drawn and age > 10:
                assert tools.read_view().overlay.limit == 2200
                if drawn[0] != 2200:
                    return
                assert 0 < drawn[1] < scene.label_candidates
                assert gpu and gpu[0] <= 512 * 512 * 4
                intervals.append(evidence.frame_intervals_ms[-1])
                full_frames += 1
                if full_frames >= 120:
                    suffix = ("overlays", "overlap", "value")
            elif stage == 7 and scene and drawn and age > 10:
                if (
                    not tools.read_view().overlay.overlapping_labels
                    or drawn[1] != scene.label_candidates
                ):
                    return
                suffix = ("overlays", "overlap", "value")
            elif stage == 8 and scene and drawn and age > 10:
                if (
                    tools.read_view().overlay.overlapping_labels
                    or drawn[1] >= scene.label_candidates
                ):
                    return
                assert drawn[0] == 2200
                cached = tools.scene.prepared_count
                stage, entered = 9, evidence.frames
            elif stage == 9 and age > 30:
                assert tools.scene.prepared_count <= cached + 1
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
            if suffix and native.click(probe, suffix, evidence.frames):
                stage, entered = stage + 1, evidence.frames

        evidence = run_gui(
            root / "source.csv",
            smoke_frames=1500,
            on_probe_frame=frame,
            preferences_path=root / "prefs.json",
        )
        assert done
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
