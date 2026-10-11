"""Common physical bins, source scopes, scoped selection and stale publication."""

from concurrent.futures import CancelledError, ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep

import numpy as np
import polars as pl
import pytest
from PIL import Image

from datelier.core.dataset import Dataset, SourceReference
from datelier.inspection.arrays.mapping import ArrayLayout, ArrayRecordMapping
from datelier.inspection.images.comparisons.jobs import ImageComparisonJobs
from datelier.inspection.images.comparisons.prepare import prepare_comparison
from datelier.inspection.images.comparisons.selection import select_dimension_bin
from datelier.inspection.images.comparisons.settings import (
    ImageComparisonSettings,
    ImageComparisonSource,
)
from datelier.inspection.images.comparisons.types import (
    ImageComparisonInput,
    PreparedImageComparison,
)
from datelier.inspection.images.profile_scan import ImageProfileScan
from datelier.inspection.images.profile_types import (
    ChannelKey,
    ImageBounds,
    ImageProfile,
    ImageProfileSettings,
    ImageProgress,
    ImageScope,
    ImageScopeMode,
    PixelScope,
)
from datelier.inspection.images.profiles import finish_image_profile
from datelier.inspection.images.storage import ImageStore
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.arrays.storage import ArrayStore
from datelier.plotting.selection import SELECTION_LIMIT


def table(path: Path, references: list[str | None]) -> Dataset:
    path.write_text("image\n")
    stat = path.stat()
    return Dataset.from_source(
        pl.DataFrame({"image": references}, schema_overrides={"image": pl.String}),
        SourceReference(path, stat.st_size, stat.st_mtime_ns),
    )


def fixture(
    root: Path,
) -> tuple[tuple[ImageComparisonInput, ...], ImageComparisonSettings]:
    for name, width, red in (
        ("a2", 2, 10),
        ("a4", 4, 30),
        ("b6", 6, 50),
        ("b2", 2, 70),
    ):
        Image.new("RGB", (width, 2), (red, 20, 30)).save(root / f"{name}.png")
    Image.new("RGBA", (4, 2), (90, 20, 30, 128)).save(root / "rgba.png")
    (root / "corrupt.png").write_bytes(b"corrupt")
    datasets = (
        table(root / "a.csv", ["a2.png", "a4.png"]),
        table(
            root / "b.csv",
            ["b6.png", "b2.png", "rgba.png", None, "missing.png", "corrupt.png"],
        ),
    )
    sources = tuple(
        ImageComparisonSource(name, ImageProfileSettings("image"))
        for name in ("a", "b")
    )
    recipe = ImageComparisonSettings(sources, 2)
    inputs = tuple(
        ImageComparisonInput(source, dataset, source.file_id, view_name="records")
        for source, dataset in zip(sources, datasets, strict=True)
    )
    return inputs, recipe


def prepare(
    inputs: tuple[ImageComparisonInput, ...], recipe: ImageComparisonSettings
) -> PreparedImageComparison:
    return prepare_comparison(inputs, recipe, Event(), ImageProgress())


def test_common_edges_weighted_colors_and_separate_physical_families(
    tmp_path: Path,
) -> None:
    inputs, recipe = fixture(tmp_path)
    before = {path: path.read_bytes() for path in tmp_path.iterdir()}
    result = prepare(inputs, recipe)
    curve = next(
        curve for curve in result.curves if curve.key == ChannelKey("RGB", "R", "|u1")
    )
    first, second = curve.counts
    assert first is not None and second is not None
    assert first.edges.tolist() == second.edges.tolist() == [10.0, 40.0, 70.0]
    assert first.counts.tolist() == [12.0, 0.0]
    assert second.counts.tolist() == [0.0, 16.0]
    assert curve.proportions[0] is not None and curve.proportions[0].counts.sum() == 1
    assert next(
        s for s in result.profiles[0].summaries if s.key == curve.key
    ).mean == pytest.approx(70 / 3)
    assert (
        next(s for s in result.profiles[1].summaries if s.key == curve.key).mean == 55
    )
    rgba = next(
        curve for curve in result.curves if curve.key == ChannelKey("RGBA", "A", "|u1")
    )
    assert rgba.counts[0] is None and rgba.counts[1] is not None
    assert rgba.counts[1].counts.sum() == 8
    assert (
        result.profiles[1].nulls,
        result.profiles[1].unresolved,
        result.profiles[1].failures,
    ) == (1, 1, 1)
    widths = next(curve for curve in result.curves if curve.key.name == "Width")
    assert all(
        chart is not None and chart.edges.tolist() == [2.0, 4.0, 6.0]
        for chart in widths.counts
    )
    assert result.profiles[0].file_id == "a" and result.profiles[1].file_id == "b"
    assert all(path.read_bytes() == data for path, data in before.items())


def test_dimension_selection_keeps_file_and_sorted_source_row_identity(
    tmp_path: Path,
) -> None:
    inputs, recipe = fixture(tmp_path)
    second = inputs[1].dataset
    inputs = (
        inputs[0],
        replace(
            inputs[1],
            dataset=second.with_rows(second.table.reverse(), second.row_ids.reverse()),
        ),
    )
    result = prepare(inputs, recipe)
    first = select_dimension_bin(result, 0, "Width", 0, inputs[0].dataset)
    selected = select_dimension_bin(result, 1, "Width", 1, inputs[1].dataset)
    assert first.origin.file_id == "a" and first.row_ids == (0,)
    assert selected.origin.file_id == "b" and set(selected.row_ids) == {0, 2}
    assert selected.first_position == 3
    assert selected.origin.view == "records"
    with pytest.raises(ValueError, match="changed"):
        select_dimension_bin(
            result,
            1,
            "Width",
            0,
            inputs[1].dataset.with_rows(second.table, second.row_ids),
        )


def test_seeded_and_linked_scopes_are_explicit_and_sort_invariant(
    tmp_path: Path,
) -> None:
    inputs, _ = fixture(tmp_path)
    sources = (
        replace(
            inputs[0].source,
            profile=ImageProfileSettings(
                "image",
                ImageScope(ImageScopeMode.RANDOM, count=1),
                PixelScope.SAMPLE,
                pixel_count=2,
                pixel_seed=5,
            ),
        ),
        replace(
            inputs[1].source,
            profile=ImageProfileSettings(
                "image",
                ImageScope(ImageScopeMode.SELECTION),
                PixelScope.SAMPLE,
                pixel_count=2,
                pixel_seed=5,
            ),
        ),
    )
    recipe = ImageComparisonSettings(sources, 2)
    inputs = tuple(
        replace(item, source=source, selection=(0,))
        for item, source in zip(inputs, sources, strict=True)
    )
    original = prepare(inputs, recipe)
    reordered = tuple(
        replace(
            item,
            dataset=item.dataset.with_rows(
                item.dataset.table.reverse(), item.dataset.row_ids.reverse()
            ),
        )
        for item in inputs
    )
    sorted_result = prepare(reordered, recipe)
    assert all(
        profile.profiled_pixels == 2 and profile.sampled_pixels
        for profile in original.profiles
    )
    assert original.profiles[1].records["row_id"].to_list() == [0]
    for first, second in zip(original.profiles, sorted_result.profiles, strict=True):
        assert first.records["row_id"].to_list() == second.records["row_id"].to_list()
        assert first.summaries == second.summaries


def test_compressed_array_is_leased_once_across_both_global_passes(
    tmp_path: Path,
) -> None:
    inputs, _ = fixture(tmp_path)
    path = tmp_path / "images.npz"
    pixels = np.zeros((2, 32, 32, 3), dtype=np.uint8)
    pixels[0] = (10, 20, 30)
    pixels[1] = (30, 20, 30)
    np.savez_compressed(path, images=pixels)
    catalog = inspect_arrays(path)
    dataset = Dataset.from_source(
        pl.DataFrame({"record_index": [0, 1]}), catalog.source
    )
    mapping = ArrayRecordMapping(
        "images", layout=ArrayLayout.IMAGE, display_axes=(1, 2), channel_axis=3
    )
    source = ImageComparisonSource("arrays", ImageProfileSettings("images"))
    arrays = ArrayStore(retained_bytes=0)
    try:
        item = ImageComparisonInput(
            source, dataset, "arrays", catalog=catalog, mapping=mapping, arrays=arrays
        )
        result = prepare(
            (item, inputs[1]), ImageComparisonSettings((source, inputs[1].source), 4)
        )
        assert (
            result.profiles[0].ready == 2 and result.profiles[0].profiled_pixels == 2048
        )
        assert arrays.extractions == 1 and arrays.stored_bytes == 0
        assert result.profiles[0].summaries[0].mean == 20
        unavailable = replace(source, profile=replace(source.profile, column="other"))
        with pytest.raises(ValueError, match="current confirmed"):
            prepare(
                (replace(item, source=unavailable), inputs[1]),
                ImageComparisonSettings((unavailable, inputs[1].source), 4),
            )
        assert arrays.extractions == 1
    finally:
        temporary = arrays.temporary_path
        arrays.close()
    assert temporary is not None and not temporary.exists()


def test_late_external_edit_rejects_earlier_finished_contributors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs, recipe = fixture(tmp_path)
    calls = 0

    def changed(
        scan: ImageProfileScan,
        images: ImageStore,
        arrays: ArrayStore,
        stop: Event,
        progress: ImageProgress,
        shared_bounds: ImageBounds | None = None,
    ) -> ImageProfile:
        nonlocal calls
        result = finish_image_profile(
            scan, images, arrays, stop, progress, shared_bounds
        )
        calls += 1
        if calls == 2:
            Image.new("RGB", (8, 2)).save(tmp_path / "a2.png")
        return result

    monkeypatch.setattr(
        "datelier.inspection.images.comparisons.prepare.finish_image_profile", changed
    )
    with pytest.raises(ValueError, match="changed"):
        prepare(inputs, recipe)


def test_invalid_and_abandoned_commands_do_not_publish_partial_data(
    tmp_path: Path,
) -> None:
    inputs, recipe = fixture(tmp_path)
    with pytest.raises(ValueError, match="two"):
        prepare(inputs[:1], recipe)
    stop = Event()
    stop.set()
    with pytest.raises(CancelledError):
        prepare_comparison(inputs, recipe, stop, ImageProgress())


def wait(
    jobs: ImageComparisonJobs,
    inputs: tuple[ImageComparisonInput, ...],
    recipe: ImageComparisonSettings,
) -> None:
    deadline = monotonic() + 5
    while jobs.busy and monotonic() < deadline:
        jobs.bind(recipe, inputs)
        jobs.poll()
        sleep(0.001)
    assert not jobs.busy


def test_jobs_start_explicitly_and_invalidate_without_rerunning(tmp_path: Path) -> None:
    inputs, recipe = fixture(tmp_path)
    jobs = ImageComparisonJobs()
    try:
        jobs.bind(recipe, inputs)
        assert jobs.active is None and jobs.started == 0 and not jobs.busy
        jobs.request()
        wait(jobs, inputs, recipe)
        assert jobs.active is not None
        jobs.bind(recipe, inputs)
        assert jobs.active is not None and jobs.started == 1
        changed = (
            replace(inputs[0], references=ReferenceSettings(roots=(str(tmp_path),))),
            inputs[1],
        )
        jobs.bind(recipe, changed)
        assert jobs.active is None and jobs.started == 1
        jobs.bind(recipe, inputs[:1])
        with pytest.raises(ValueError, match="recover"):
            jobs.request()
    finally:
        jobs.close()


def test_executing_results_and_selection_cannot_publish_after_source_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs, recipe = fixture(tmp_path)
    result = prepare(inputs, recipe)
    entered, release = Event(), Event()

    def controlled(
        inputs: tuple[ImageComparisonInput, ...],
        recipe: ImageComparisonSettings,
        stop: Event,
        progress: ImageProgress,
    ) -> PreparedImageComparison:
        entered.set()
        assert release.wait(5)
        return result

    monkeypatch.setattr(
        "datelier.inspection.images.comparisons.jobs.prepare_comparison", controlled
    )
    with ThreadPoolExecutor(1) as executor:
        jobs = ImageComparisonJobs(executor)
        try:
            jobs.bind(recipe, inputs)
            jobs.poll()
            jobs.request()
            assert entered.wait(5)
            jobs.bind(recipe, inputs[:1])
            release.set()
            wait(jobs, inputs[:1], recipe)
            assert jobs.active is None
        finally:
            release.set()
            jobs.close()
    monkeypatch.setattr(
        "datelier.inspection.images.comparisons.jobs.prepare_comparison",
        prepare_comparison,
    )
    jobs = ImageComparisonJobs()
    try:
        jobs.bind(recipe, inputs)
        jobs.request()
        wait(jobs, inputs, recipe)
        assert jobs.active is not None
        jobs.request_selection(jobs.active, 1, "Width", 0, inputs[1].dataset)
        deadline = monotonic() + 5
        while monotonic() < deadline and not jobs.selection_message.startswith(
            "Mapped"
        ):
            assert jobs.poll_selection({"a": inputs[0].dataset}) is None
            sleep(0.001)
        assert "closed" in jobs.selection_message
    finally:
        jobs.close()


def test_large_dimension_selection_reports_all_matches_and_bounds_publication(
    tmp_path: Path,
) -> None:
    inputs, recipe = fixture(tmp_path)
    original = prepare(inputs, recipe)
    count = SELECTION_LIMIT + 1
    dataset = Dataset.from_source(
        pl.DataFrame({"image": ["a2.png"] * count}), inputs[0].dataset.source
    )
    records = pl.DataFrame(
        {
            "row_id": range(count),
            "position": range(count),
            "status": ["Ready"] * count,
            "width": [2] * count,
        },
        schema_overrides={
            "row_id": pl.UInt64,
            "position": pl.UInt64,
            "width": pl.UInt64,
        },
    )
    profile = replace(original.profiles[0], revision=dataset.revision, records=records)
    result = replace(original, profiles=(profile, original.profiles[1]))
    selected = select_dimension_bin(result, 0, "Width", 0, dataset)
    assert selected.matches == count and len(selected.row_ids) == SELECTION_LIMIT
    assert selected.row_ids[0] == 0 and selected.row_ids[-1] == SELECTION_LIMIT - 1
    assert selected.first_position == 0 and selected.origin.revision == dataset.revision
