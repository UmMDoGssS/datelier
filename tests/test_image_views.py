"""Image-space navigation, exact versus overview pixels and saved file controls."""

from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

import pytest
from PIL import Image

from datelier.application.editor import EditorController
from datelier.application.workspace import capture_session
from datelier.inspection.images.settings import ImageSettings
from datelier.inspection.images.types import ImageDisplay, ImageWindow
from datelier.inspection.images.viewport import ImageViewport
from datelier.workspace.recipes.codec import decode, encode
from datelier.workspace.sessions.jobs import save_snapshot
from datelier.workspace.single import WorkspaceViews


def test_zoom_keeps_pixel_under_pointer_and_pan_uses_image_units() -> None:
    view = ImageViewport(1, 100, 200)
    point = view.point(80, 60)
    zoomed = view.zoom_at(4, 80, 60)
    assert zoomed.point(80, 60) == point
    assert zoomed.pan(-40, -20) == ImageViewport(4, zoomed.left + 10, zoomed.top + 5)
    assert zoomed.clamp(10, 20, (400, 300)) == ImageViewport(4, 0, 0)
    assert zoomed.window((400, 300)).width == 101


@pytest.mark.parametrize(
    "settings",
    [
        ImageSettings(viewport=ImageViewport(float("nan"))),
        ImageSettings(viewport=ImageViewport(left=float("inf"))),
        ImageSettings(display=ImageDisplay(value_range=(1, 1))),
        ImageSettings(gpu_bytes=100),
    ],
)
def test_invalid_saved_image_controls_are_rejected(settings: ImageSettings) -> None:
    with pytest.raises(ValueError):
        settings.validate()


def test_legacy_view_defaults_and_strict_image_recipe_roundtrip() -> None:
    saved = WorkspaceViews(
        image=ImageSettings(ImageDisplay(2, (-5, 10)), ImageViewport(3, 40, 20))
    )
    assert decode(WorkspaceViews, encode(saved)) == saved
    legacy = encode(WorkspaceViews())
    assert isinstance(legacy, dict)
    legacy.pop("image")
    decoded = decode(WorkspaceViews, legacy)
    assert isinstance(decoded, WorkspaceViews) and decoded.image == ImageSettings()


def wait(editor: EditorController) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if not editor.workspace.busy and all(
            (not file.loader.status.path or file.loader.active is not None)
            and not file.images.jobs.busy
            and not file.references.busy
            for file in editor.files
        ):
            return
        sleep(0.001)
    raise AssertionError("Image session did not finish")


def test_independent_image_windows_and_restoration_never_decode_whole_collections(
    tmp_path: Path,
) -> None:
    for index in range(2):
        Image.new("RGB", (2048, 1536), (7 + index, 8, 9)).save(
            tmp_path / f"image{index}.png"
        )
        (tmp_path / f"source{index}.csv").write_text(
            f"id,image,label\n1,image{index}.png,file-{index}\n"
        )
    originals = [path.read_bytes() for path in sorted(tmp_path.glob("image*.png"))]
    workspace = tmp_path / "session.datelier.json"
    editor = EditorController()
    try:
        files = [editor.new_file(tmp_path / f"source{index}.csv") for index in range(2)]
        wait(editor)
        for file in files:
            assert file.loader.active is not None
            file.images.jobs.request_record(file.loader.active.dataset, "image", 0)
        wait(editor)
        for file in files:
            file.images.jobs.request_window(
                ImageWindow(0, 0, 2048, 1536), ImageDisplay(), file.arrays.store
            )
        wait(editor)
        first, second = (file.images.jobs.active for file in files)
        assert first is not None and second is not None
        assert first.locator.origin.row_id == second.locator.origin.row_id == 0
        assert first.locator.origin.file_id != second.locator.origin.file_id
        assert first.window.step > 1 and first.pixel(0, 0) == (7, 8, 9)
        assert first.pixel(1, 0) is None and second.pixel(0, 0) == (8, 8, 9)
        files[0].images.settings = ImageSettings(
            ImageDisplay(1), ImageViewport(2, 40, 20)
        )
        files[0].records.settings = replace(files[0].records.settings, gallery=False)
        files[0].views = replace(files[0].views, tab="Inspect")
        save_snapshot(workspace, capture_session(editor), False)
        temporary = files[0].images.jobs.store.temporary_path
        editor.close_file(files[0].identity)
    finally:
        editor.close()
    assert temporary is not None and not temporary.exists()
    restored = EditorController()
    try:
        restored.open_workspace(workspace)
        wait(restored)
        first_file = next(
            file
            for file in restored.files
            if file.loader.status.path and file.loader.status.path.name == "source0.csv"
        )
        assert first_file.images.settings == ImageSettings(
            ImageDisplay(1), ImageViewport(2, 40, 20)
        )
        assert first_file.views.tab == "Inspect"
        for file in restored.files:
            assert file.images.jobs.metadata is None and file.images.jobs.active is None
            assert file.images.jobs.store.temporary_path is None
        assert originals == [
            path.read_bytes() for path in sorted(tmp_path.glob("image*.png"))
        ]
    finally:
        restored.close()
