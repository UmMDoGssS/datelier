"""Visible array thumbnails keep provenance, bounded retention and stale isolation."""

from dataclasses import replace
from pathlib import Path

import numpy as np
from PIL import Image
from test_rebuild_sources import until

from datelier.application.sessions import EditorController
from datelier.inspection.records import RecordCard, RecordField
from datelier.pipeline import Sort


def card(row: int, position: int | None = None) -> RecordCard:
    return RecordCard(
        row,
        position if position is not None else row,
        RecordField("pixels", "array"),
        (),
    )


def test_gallery_is_lazy_sampled_scoped_and_uses_original_rows_after_sort(
    tmp_path: Path,
) -> None:
    source = tmp_path / "pictures.npz"
    values = np.stack(
        [np.full((257, 513), row * 40, dtype=np.uint8) for row in range(4)]
    )
    np.savez_compressed(source, pixels=values, priority=np.array([4, 1, 3, 2]))
    original = source.read_bytes()
    editor = EditorController()
    try:
        file = editor.active
        file.open(source)
        until(editor, lambda: file.inspection is not None)
        assert file.gallery.pending == 0 and not file.gallery.previews
        assert file.images.jobs.metadata is None and file.arrays.active is None
        assert file.references.source is None  # Array aliases never scan nearby files.
        assert file.gallery.supports(card(0))
        file.images.settings = replace(
            file.images.settings,
            display=replace(file.images.settings.display, value_range=(0, 120)),
        )
        editor.poll()
        for row in range(4):
            file.gallery.get(card(row))
        assert file.gallery.pending == 2
        until(editor, lambda: file.gallery.pending == 0)
        preview, message = file.gallery.get(card(1))
        assert preview and not message and preview.step == 5
        assert preview.rgba.shape == (52, 103, 4)
        assert preview.origin.row_id == 1 and preview.origin.file_id == file.identity
        assert preview.rgba.flags.writeable is False
        assert preview.rgba[0, 0, 0] == 85
        other = editor.new_file(source)
        until(editor, lambda: other.inspection is not None)
        other.gallery.get(card(1))
        until(editor, lambda: other.gallery.pending == 0)
        different, _ = other.gallery.get(card(1))
        assert different and different.origin != preview.origin
        file.editor.request(Sort(("priority",)))
        until(editor, lambda: not file.editor.busy)
        assert not file.gallery.previews
        assert file.inspection and file.inspection.dataset.row_ids.to_list() == [
            1,
            3,
            2,
            0,
        ]
        file.gallery.get(card(1, 0))
        until(editor, lambda: file.gallery.pending == 0)
        sorted_preview, _ = file.gallery.get(card(1, 0))
        assert sorted_preview and sorted_preview.origin.row_id == 1
        assert sorted_preview.origin.revision != preview.origin.revision
        np.testing.assert_array_equal(sorted_preview.rgba, preview.rgba)
        _, message = file.gallery.get(card(3, 0))
        assert message == "Record changed; refresh its gallery page."
        assert (
            not file.analysis.jobs.results and file.images.profile_jobs.active is None
        )
        assert source.read_bytes() == original
    finally:
        editor.close()


def test_gallery_budget_close_and_configuration_abandon_obsolete_previews(
    tmp_path: Path,
) -> None:
    source = tmp_path / "pictures.npz"
    np.savez_compressed(
        source,
        pixels=np.zeros((4, 512, 1024), dtype=np.uint8),
        image=np.array(["ref.png"] * 4),
    )
    Image.new("RGB", (512, 512), (50, 60, 70)).save(tmp_path / "ref.png")
    editor = EditorController()
    try:
        file = editor.active
        file.open(source)
        until(editor, lambda: file.inspection is not None)
        file.references.configure(
            replace(file.references.settings, thumbnail_size=512, cpu_bytes=1024 * 1024)
        )
        editor.poll()
        for row in range(4):
            file.gallery.get(card(row))
        assert file.gallery.pending == 2
        until(editor, lambda: file.gallery.pending == 0)
        assert (
            file.gallery.retained_bytes + file.references.retained_bytes <= 1024 * 1024
        )
        assert len(file.gallery.previews) == 1

        def reference_ready() -> bool:
            return file.references.get("image", "ref.png")[1] is not None

        until(editor, reference_ready)
        _, reference = file.references.get("image", "ref.png")
        assert reference and reference.rgba is not None
        assert reference.rgba.shape[0] < 512 and "preview" in reference.description
        assert (
            file.gallery.retained_bytes + file.references.retained_bytes <= 1024 * 1024
        )
        file.gallery.get(card(2))
        file.images.settings = replace(
            file.images.settings,
            display=replace(file.images.settings.display, value_range=(0, 5)),
        )
        editor.poll()
        assert not file.gallery.previews and file.gallery.pending == 0
        file.gallery.get(card(3))
        file.close()
        editor.poll()
        assert file.gallery.closed and not file.gallery.previews
        assert file.gallery.get(card(0)) == (None, "")
    finally:
        editor.close()
