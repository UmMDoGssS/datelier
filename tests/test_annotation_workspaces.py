"""Saved association recipes reopen idle, without parsing labels or image pixels."""

from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep
from unittest.mock import patch

from PIL import Image

from datelier.application.annotations.navigation import open_rows
from datelier.application.editor import EditorController
from datelier.application.workspace import capture_session
from datelier.inspection.annotations.association_types import PreparedAnnotations
from datelier.inspection.annotations.overlay import OverlayClass, OverlaySettings
from datelier.inspection.annotations.settings import (
    AnnotationSettings,
    AnnotationSource,
    ImageAssociationMapping,
    ImageMatch,
)
from datelier.inspection.annotations.types import AnnotationClass, AnnotationFormat
from datelier.inspection.annotations.view_settings import AnnotationViewSettings
from datelier.plotting.scatter import SELECTION_LIMIT
from datelier.workspace.recipes.codec import decode_record, encode
from datelier.workspace.sessions.jobs import save_snapshot
from datelier.workspace.single import WorkspaceViews


def wait(editor: EditorController) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if not editor.workspace.busy and all(
            (not file.loader.status.path or file.loader.active is not None)
            and not file.images.annotations.busy
            and not file.references.busy
            for file in editor.files
        ):
            return
        sleep(0.001)
    raise AssertionError("Annotation workspace did not finish")


def test_legacy_image_defaults_and_explicit_annotation_source_roundtrip() -> None:
    recipe = AnnotationSettings(
        "image",
        (
            AnnotationSource(
                "truth",
                "labels.txt",
                AnnotationFormat.YOLO,
                classes=(AnnotationClass(0, "cat"),),
                scores=True,
                match=ImageMatch.STEM,
                mappings=(ImageAssociationMapping("labels", 0, "original key"),),
            ),
        ),
    )
    assert decode_record(AnnotationSettings, encode(recipe)) == recipe
    raw = encode(WorkspaceViews())
    assert isinstance(raw, dict) and isinstance(raw["image"], dict)
    raw["image"].pop("annotations")
    assert decode_record(WorkspaceViews, raw) == WorkspaceViews()


def test_saved_confirmed_row_mapping_restores_without_implicit_reading(
    tmp_path: Path,
) -> None:
    Image.new("RGB", (20, 10)).save(tmp_path / "scene.png")
    source = tmp_path / "table.csv"
    source.write_text("id,image,label\n0,scene.png,cat\n")
    labels = tmp_path / "labels.txt"
    labels.write_text("0 0.5 0.5 1 1\n")
    workspace = tmp_path / "session.datelier.json"
    editor = EditorController()
    expected = None
    view = AnnotationViewSettings(
        overlay=OverlaySettings(
            sources=("truth",),
            classes=(OverlayClass("truth", 0),),
            minimum_score=0.5,
            labels=False,
        ),
        tab="Profiles",
        profile_tab="Quality",
        distribution="Aspect ratio",
        bins=12,
    )
    try:
        file = editor.new_file(source)
        wait(editor)
        file.images.settings = replace(
            file.images.settings,
            annotations=AnnotationSettings(
                "image",
                (
                    AnnotationSource(
                        "truth",
                        str(labels),
                        AnnotationFormat.YOLO,
                        match=ImageMatch.STEM,
                        mappings=(ImageAssociationMapping("labels", 0),),
                    ),
                ),
            ),
        )
        editor.poll()
        file.images.annotations.request()
        wait(editor)
        assert file.images.annotations.active is not None
        expected = file.images.settings.annotations
        assert expected.sources[0].mappings[0].expected_key is not None
        ready = file.images.annotations.active
        file.images.settings = replace(file.images.settings, annotation_view=view)
        editor.poll()
        assert (
            file.images.annotations.active is ready and not file.images.annotations.busy
        )
        assert file.images.annotation_profiles.active is None
        save_snapshot(workspace, capture_session(editor), False)
    finally:
        editor.close()
    restored = EditorController()
    try:
        with (
            patch(
                "datelier.inspection.annotations.prepare.load_annotations",
                side_effect=AssertionError("restore parsed labels"),
            ),
            patch.object(
                Image.Image,
                "load",
                side_effect=AssertionError("restore decoded pixels"),
            ),
        ):
            restored.open_workspace(workspace)
            wait(restored)
        file = restored.active
        assert file.images.settings.annotations == expected
        assert file.images.settings.annotation_view == view
        assert (
            file.images.annotation_profiles.active is None
            and not file.images.annotation_profiles.busy
        )
        assert (
            file.images.annotations.active is None and not file.images.annotations.busy
        )
        assert file.images.jobs.store.temporary_path is None
    finally:
        restored.close()


def test_large_class_links_publish_bounded_rows_and_ignore_stale_profiles(
    tmp_path: Path,
) -> None:
    source = tmp_path / "images.csv"
    count = SELECTION_LIMIT + 3
    source.write_text("image\n" + "scene.png\n" * count)
    editor = EditorController()
    try:
        file = editor.new_file(source)
        wait(editor)
        assert file.loader.active is not None
        dataset = file.loader.active.dataset
        prepared = PreparedAnnotations(
            file.identity, file.view_name, dataset.revision, "image", ()
        )
        assert open_rows(
            file.records, prepared, file.identity, file.view_name, tuple(range(count))
        )
        assert file.selection.row_ids == frozenset(range(SELECTION_LIMIT))
        assert "10,003 matching" in file.selection.message
        assert "first 10,000" in file.selection.message
        assert file.records.settings.gallery is False
        assert not open_rows(
            file.records,
            replace(prepared, file_id="other-file"),
            file.identity,
            file.view_name,
            (count - 1,),
        )
        assert file.selection.row_ids == frozenset(range(SELECTION_LIMIT))
    finally:
        editor.close()
