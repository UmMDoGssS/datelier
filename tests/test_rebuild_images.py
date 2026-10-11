"""Explicit image profiles, source-aligned opening and numeric display recipes."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep

import numpy as np
from PIL import Image

from datelier.application.editor import EditorController
from datelier.application.profiles import ProfileFamily
from datelier.inspection.arrays.mapping import (
    ArrayLayout,
    ArrayRecordMapping,
    SupportingArray,
)
from datelier.inspection.heatmaps import Colormap
from datelier.inspection.images.profiles import (
    ImageScope,
    ImageScopeMode,
    PixelScope,
)
from datelier.inspection.images.types import ImageDisplay, ImageWindow
from datelier.pipeline.operations import SelectColumns, Sort


def until(editor: EditorController, condition: Callable[[], bool]) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        editor.poll()
        if condition():
            return
        sleep(0.001)
    raise AssertionError(editor.current.images.profile_jobs.message)


def test_exact_then_seeded_selection_profile_and_original_record_navigation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "records.csv"
    Image.new("RGB", (4, 2), (10, 20, 30)).save(tmp_path / "a.png")
    Image.new("RGB", (2, 2), (40, 50, 60)).save(tmp_path / "b.png")
    source.write_text("image,label\na.png,a\nb.png,b\n,empty\nmissing.png,missing\n")
    original = source.read_bytes()
    editor = EditorController()
    try:
        file = editor.active
        file.open(source)
        until(editor, lambda: file.inspection is not None and not file.references.busy)
        file.profiles.choose(("image",))
        editor.poll()
        assert file.profiles.family == ProfileFamily.IMAGES
        assert (
            file.images.profile_jobs.active is None
            and not file.images.profile_jobs.busy
        )
        editor.choose_route("Correlations")
        file.images.request_collection("image")
        until(editor, lambda: file.images.profile_jobs.active is not None)
        profile = file.images.profile_jobs.active
        assert (
            profile
            and profile.ready == 2
            and profile.nulls == 1
            and profile.unresolved == 1
        )
        assert profile.profiled_pixels == profile.total_pixels == 12
        assert profile.summaries[0].mean == 20
        assert len(file.images.statistics) == 6
        assert file.views.tab == "Correlations" and file.images.jobs.metadata is None
        row = profile.records.row(1, named=True)
        assert file.records.open_position(
            profile.revision, int(row["position"]), int(row["row_id"]), "image"
        )
        assert not file.records.open_position(profile.revision, 0, 1, "image")
        assert file.records.settings.start == 2 and file.selection.row_ids == {1}
        file.images.settings = replace(
            file.images.settings,
            profile=replace(
                file.images.settings.profile,
                scope=ImageScope(ImageScopeMode.SELECTION),
                pixels=PixelScope.SAMPLE,
                pixel_count=2,
                pixel_seed=7,
            ),
        )
        editor.poll()
        assert file.images.profile_jobs.active is None
        file.images.request_collection("image")
        until(editor, lambda: file.images.profile_jobs.active is not None)
        sample = file.images.profile_jobs.active
        assert (
            sample
            and sample.records["row_id"].to_list() == [1]
            and sample.profiled_pixels == 2
        )
        assert sample.total_pixels == 4 and sample.sampled_pixels
        assert source.read_bytes() == original
    finally:
        editor.close()


def test_mapped_image_profile_uses_original_rows_and_supporting_field_stays_scalar(
    tmp_path: Path,
) -> None:
    source = tmp_path / "images.npz"
    values = np.arange(24, dtype=np.uint8).reshape(3, 2, 4)
    np.savez_compressed(
        source, images=values, labels=np.array([3, 1, 2]), wrong=np.arange(2)
    )
    original = source.read_bytes()
    editor = EditorController()
    try:
        owner = editor.active
        owner.open(source)
        until(editor, lambda: owner.inspection is not None)
        view = owner.record_views.open_array(
            owner,
            ArrayRecordMapping(
                "images",
                layout=ArrayLayout.IMAGE,
                display_axes=(1, 2),
                supporting=(SupportingArray("labels", "label"),),
            ),
        )
        until(editor, lambda: view.inspection is not None)
        view.editor.request(Sort(("label",)))
        until(editor, lambda: not view.editor.busy)
        view.images.request_collection("record_index")
        until(editor, lambda: view.images.profile_jobs.active is not None)
        profile = view.images.profile_jobs.active
        assert profile and profile.records["row_id"].to_list() == [1, 2, 0]
        assert profile.settings.column == "images" and profile.ready == 3
        view.editor.request(SelectColumns(("label",)))
        until(editor, lambda: not view.editor.busy)
        view.images.request_collection("images")
        until(editor, lambda: view.images.profile_jobs.active is not None)
        assert (
            view.images.profile_jobs.active
            and view.images.profile_jobs.active.ready == 3
        )
        view.images.request_record("label", 0)
        until(editor, lambda: not view.images.jobs.busy)
        assert (
            view.images.jobs.metadata is None and "requires" in view.images.jobs.message
        )
        assert source.read_bytes() == original
    finally:
        editor.close()


def test_heatmap_channel_slice_and_range_leave_original_values_unchanged(
    tmp_path: Path,
) -> None:
    source = tmp_path / "heatmaps.npz"
    values = np.arange(2 * 3 * 4 * 5 * 6, dtype=np.float64).reshape(2, 3, 4, 5, 6)
    np.savez_compressed(source, grids=values, wrong=np.arange(7))
    original = source.read_bytes()
    editor = EditorController()
    try:
        owner = editor.active
        owner.open(source)
        until(editor, lambda: owner.inspection is not None)
        view = owner.record_views.open_array(
            owner,
            ArrayRecordMapping(
                "grids", layout=ArrayLayout.HEATMAP, display_axes=(3, 4), channel_axis=1
            ),
        )
        until(editor, lambda: view.inspection is not None)
        view.images.request_record("grids", 1)
        until(editor, lambda: view.images.jobs.metadata is not None)
        assert view.images.fixed_axes == ((2, 4),)
        view.images.set_fixed_coordinate(2, 3)
        view.images.settings = replace(
            view.images.settings,
            display=replace(
                view.images.settings.display,
                channel=2,
                value_range=(-20, 1000),
                colormap=Colormap.BLUE_YELLOW,
            ),
        )
        view.images.request_window(ImageWindow(0, 0, 6, 5))
        until(editor, lambda: view.images.jobs.active is not None)
        prepared = view.images.jobs.active
        assert prepared and prepared.pixel(2, 1) == (float(values[1, 2, 3, 1, 2]),)
        np.testing.assert_array_equal(prepared.raw, values[1, 2, 3])
        assert prepared.display == ImageDisplay(
            2, (-20, 1000), Colormap.BLUE_YELLOW, (0, 0, 3, 0, 0)
        )
        assert source.read_bytes() == original
    finally:
        editor.close()
