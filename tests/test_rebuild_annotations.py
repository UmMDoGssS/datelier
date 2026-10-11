"""Independent annotation recipes and latest-only scenes preserve source records."""

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

from PIL import Image

from datelier.application.annotations.navigation import open_rows
from datelier.application.sessions import EditorController
from datelier.inspection.annotations.overlay import OverlayClass, OverlaySettings
from datelier.inspection.annotations.settings import AnnotationSource
from datelier.inspection.annotations.types import AnnotationFormat
from datelier.inspection.images.types import ImageWindow
from datelier.inspection.images.viewport import ImageViewport


def until(editor: EditorController, condition: Callable[[], bool]) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if condition():
            return
        sleep(0.001)
    raise AssertionError(editor.current.images.annotations.message)


def fixture(root: Path, count: int = 100) -> tuple[Path, Path]:
    Image.new("RGB", (100, 100), (12, 24, 36)).save(root / "scene.png")
    source, labels = root / "source.csv", root / "labels.json"
    source.write_text("image\nscene.png\n")
    labels.write_text(
        json.dumps(
            {
                "images": [
                    {"id": 1, "file_name": "scene.png", "width": 100, "height": 100}
                ],
                "categories": [{"id": 1, "name": "cat"}],
                "annotations": [
                    {
                        "id": index,
                        "image_id": 1,
                        "category_id": 1,
                        "bbox": [5, 5, 40, 40],
                    }
                    for index in range(count)
                ],
            }
        )
    )
    return source, labels


def test_sources_profiles_and_overlay_filters_have_independent_drafts(
    tmp_path: Path,
) -> None:
    source, labels = fixture(tmp_path)
    originals = (
        source.read_bytes(),
        labels.read_bytes(),
        (tmp_path / "scene.png").read_bytes(),
    )
    editor = EditorController()
    try:
        first = editor.active
        first.open(source)
        second = editor.new_file(source)
        until(
            editor,
            lambda: (
                first.inspection is not None
                and second.inspection is not None
                and not first.references.busy
                and not second.references.busy
            ),
        )
        tools = first.images.annotation_tools
        assert tools.jobs.active is None and tools.profiles.active is None
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
        tools.request("image")
        until(editor, lambda: tools.jobs.active is not None)
        prepared = tools.jobs.active
        assert (
            prepared
            and len(prepared.sources) == 2
            and len(prepared.sources[0].boxes) == 100
        )
        assert first.images.jobs.metadata is None and tools.profiles.active is None
        assert second.images.annotations.active is None
        assert second.images.settings.annotations.sources == ()
        tools.request_profiles()
        until(editor, lambda: tools.profiles.active is not None)
        profiles = tools.profiles.active
        assert profiles and profiles.sources[0].classes[0].count == 100
        tools.write_view(
            replace(
                tools.read_view(),
                overlay=OverlaySettings(
                    sources=("pred",), classes=(OverlayClass("pred", 1),)
                ),
                height=260,
            )
        )
        editor.poll()
        assert tools.jobs.active is prepared and tools.profiles.active is profiles
        assert tools.source_choices[0].label == "Ground truth"
        assert tools.class_selection() == ("pred:0",)
        assert open_rows(first.records, prepared, first.identity, first.view_name, (0,))
        assert not open_rows(
            second.records, prepared, second.identity, second.view_name, (0,)
        )
        tools.apply_source(replace(prepared.sources[0].recipe, name="Edited"))
        assert tuple(s.id for s in tools.read_settings().sources) == ("truth", "pred")
        editor.poll()
        assert tools.jobs.active is None and tools.profiles.active is None
        assert originals == (
            source.read_bytes(),
            labels.read_bytes(),
            (tmp_path / "scene.png").read_bytes(),
        )
    finally:
        editor.close()


def test_cached_dense_scenes_limit_visible_boxes_avoid_labels_and_reject_old_views(
    tmp_path: Path,
) -> None:
    source, labels = fixture(tmp_path, 4000)
    editor = EditorController()
    try:
        file = editor.active
        file.open(source)
        until(editor, lambda: file.inspection is not None and not file.references.busy)
        tools = file.images.annotation_tools
        tools.apply_source(
            AnnotationSource("truth", str(labels), AnnotationFormat.COCO)
        )
        tools.request("image")
        until(editor, lambda: tools.jobs.active is not None)
        file.images.request_record("image", 0)
        until(editor, lambda: file.images.jobs.metadata is not None)
        file.images.request_window(ImageWindow(0, 0, 100, 100))
        until(editor, lambda: file.images.jobs.active is not None)
        image = file.images.jobs.active
        assert image
        settings = OverlaySettings(limit=1000)
        args = (
            image.locator.origin,
            (0.0, 0.0, 100.0, 100.0),
            ImageViewport(),
            settings,
            None,
            14.0,
        )
        tools.scene.request(*args)
        until(editor, lambda: tools.scene.active is not None)
        scene = tools.scene.active
        assert scene and scene.visible_count == 4000 and len(scene.boxes) == 1000
        assert len(scene.strokes) == 1
        assert len(scene.labels) == 1 and scene.label_candidates == 1000
        count = tools.scene.prepared_count
        for _ in range(8):
            tools.scene.request(*args)
            editor.poll()
        assert tools.scene.active is scene and tools.scene.prepared_count == count
        tools.scene.request(
            image.locator.origin,
            (0, 0, 100, 100),
            ImageViewport(),
            replace(settings, enabled=False),
            None,
            14,
        )
        assert tools.scene.active is None
        tools.scene.request(*args)
        tools.scene.request(
            replace(image.locator.origin, view_name="other"),
            (0, 0, 100, 100),
            ImageViewport(),
            settings,
            None,
            14,
        )
        editor.poll()
        assert tools.scene.active is None
        prepared = tools.jobs.active
        assert prepared
        editor.close_file(file.identity)
        assert not open_rows(
            file.records, prepared, file.identity, file.view_name, (0,)
        )
        assert tools.jobs.closed and tools.scene.closed
    finally:
        editor.close()
