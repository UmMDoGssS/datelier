"""Saved image profile recipes retain scoped fields and require explicit reruns."""

from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

from PIL import Image

from datelier.application.editor import EditorController
from datelier.application.workspace import capture_session
from datelier.inspection.images.profiles import (
    ImageProfileSettings,
    ImageScope,
    ImageScopeMode,
    PixelScope,
)
from datelier.inspection.images.settings import ImageProfileViewSettings
from datelier.inspection.references.types import ReferenceSettings
from datelier.workspace.recipes.codec import decode_record, encode
from datelier.workspace.sessions.jobs import save_snapshot
from datelier.workspace.single import WorkspaceViews


def wait(editor: EditorController) -> None:
    end = monotonic() + 5
    while monotonic() < end:
        editor.poll()
        if not editor.workspace.busy and all(
            (not file.loader.status.path or file.loader.active is not None)
            and not file.references.busy
            and not file.images.profile_jobs.busy
            for file in editor.files
        ):
            return
        sleep(0.001)
    raise AssertionError("Image profile session did not finish")


def test_image_profile_fields_and_old_image_defaults_roundtrip() -> None:
    views = WorkspaceViews()
    raw = encode(views)
    assert isinstance(raw, dict) and isinstance(raw["image"], dict)
    image = raw["image"]
    for key in ("profile", "profile_view", "profile_payload"):
        image.pop(key)
    assert decode_record(WorkspaceViews, raw) == views


def test_profile_selection_and_saved_settings_restore_without_collection_work(
    tmp_path: Path,
) -> None:
    Image.new("RGB", (3, 2), (10, 20, 30)).save(tmp_path / "image.png")
    for name in ("a", "b"):
        (tmp_path / f"{name}.csv").write_text(
            "id,image,label\n0,image.png,first\n1,image.png,second\n"
        )
    workspace = tmp_path / "session.datelier.json"
    editor = EditorController()
    expected = None
    try:
        files = [editor.new_file(tmp_path / f"{name}.csv") for name in ("a", "b")]
        for file in files:
            file.references.configure(ReferenceSettings(roots=(str(tmp_path),)))
        wait(editor)
        for file in files:
            assert file.loader.active is not None
            file.selection.choose(file.loader.active.dataset.revision, (1,))
            file.images.settings = replace(
                file.images.settings,
                profile=ImageProfileSettings(
                    "image",
                    ImageScope(ImageScopeMode.SELECTION),
                    PixelScope.SAMPLE,
                    pixel_count=3,
                ),
                profile_view=ImageProfileViewSettings(
                    "Colors", group_mode="RGB", group_dtype="|u1", height=240
                ),
            )
            file.profiles.choose(("image",))
            editor.poll()
            assert (
                file.images.profile_jobs.active is None
                and not file.images.profile_jobs.busy
            )
            file.images.profile_jobs.request()
        wait(editor)
        first, second = (file.images.profile_jobs.active for file in files)
        assert first is not None and second is not None
        assert (
            first.records["row_id"].to_list()
            == second.records["row_id"].to_list()
            == [1]
        )
        assert first.file_id != second.file_id
        assert first.profiled_pixels == 3 and first.sampled_pixels
        assert files[0].loader.active is not None
        expected = files[0].images.settings
        assert files[0].records.open_position(first.revision, 1, 1, "image")
        files[0].table.go_to(1)
        assert files[0].selection.row_ids == {1}
        assert files[0].table.target_row == 2 and not files[0].records.settings.gallery
        files[0].views = replace(files[0].views, tab="Profiles")
        save_snapshot(workspace, capture_session(editor), False)
        assert '"kind": "ImageProfile"' not in workspace.read_text()
    finally:
        editor.close()
    restored = EditorController()
    try:
        restored.open_workspace(workspace)
        wait(restored)
        file = next(
            file
            for file in restored.files
            if file.loader.status.path and file.loader.status.path.name == "a.csv"
        )
        assert file.images.settings == expected
        assert file.profiles.selected == ("image",)
        assert file.selection.row_ids == {1}
        for file in restored.files:
            assert (
                file.images.profile_jobs.active is None
                and not file.images.profile_jobs.busy
            )
            assert file.images.jobs.store.temporary_path is None
    finally:
        restored.close()
