"""Saved association recipes reopen idle, without parsing labels or image pixels."""

from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep
from unittest.mock import patch

from PIL import Image

from datelier.gui.editor_session import EditorSession
from datelier.gui.workspace.capture import capture_session
from datelier.inspection.annotations.settings import (
    AnnotationSettings,
    AnnotationSource,
    ImageAssociationMapping,
    ImageMatch,
)
from datelier.inspection.annotations.types import AnnotationClass, AnnotationFormat
from datelier.workspace.codec import decode_record, encode
from datelier.workspace.session_jobs import save_snapshot
from datelier.workspace.types import WorkspaceViews


def wait(editor: EditorSession) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if not editor.workspace_jobs.busy and all(
            (not file.controls.path or file.loader.active is not None)
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
    editor = EditorSession()
    expected = None
    try:
        file = editor.new_tab(source)
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
        file.images.sync(file)
        file.images.annotations.request()
        wait(editor)
        assert file.images.annotations.active is not None
        expected = file.images.settings.annotations
        assert expected.sources[0].mappings[0].expected_key is not None
        save_snapshot(workspace, capture_session(editor), False)
    finally:
        editor.close()
    restored = EditorSession()
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
        assert (
            file.images.annotations.active is None and not file.images.annotations.busy
        )
        assert file.images.jobs.store.temporary_path is None
    finally:
        restored.close()
