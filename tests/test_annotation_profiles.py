"""Known box/class/quality statistics, orientation/picking and obsolete jobs."""

from concurrent.futures import CancelledError, ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest

from datelier.core.dataset import DatasetRevision
from datelier.inspection.annotations.association_types import (
    AssociatedBox,
    AssociatedImage,
    AssociatedSource,
    PreparedAnnotations,
)
from datelier.inspection.annotations.geometry import oriented_box
from datelier.inspection.annotations.overlay import (
    OverlayClass,
    OverlaySettings,
    hits,
    screen_box,
    visible,
)
from datelier.inspection.annotations.profile_jobs import AnnotationProfileJobs
from datelier.inspection.annotations.profile_types import AnnotationProfiles
from datelier.inspection.annotations.profiles import prepare_profiles
from datelier.inspection.annotations.settings import AnnotationSource
from datelier.inspection.annotations.types import (
    AnnotationCatalog,
    AnnotationFormat,
    AnnotationImage,
    AnnotationIssue,
    BoxCoordinates,
    BoxRecord,
    PixelBox,
)
from datelier.inspection.images.profile_types import ImageProgress
from datelier.inspection.images.types import ImageOrigin
from datelier.inspection.images.viewport import ImageViewport
from datelier.inspection.references.types import AssetIdentity


def prepared() -> PreparedAnnotations:
    revision = DatasetRevision(uuid4())
    origin = ImageOrigin("file", "records", revision, 7, "image")
    asset = AssetIdentity(Path("annotations.json"), 100, 1)
    boxes = []
    for index, (class_id, name, xyxy, score) in enumerate(
        (
            (7, "person", (0.0, 0.0, 10.0, 20.0), 0.9),
            (7, "person", (10.0, 10.0, 40.0, 20.0), None),
            (1, "car", (-5.0, 0.0, 5.0, 10.0), 0.3),
        )
    ):
        record = BoxRecord(
            asset,
            index,
            "11",
            str(index),
            class_id,
            name,
            xyxy,
            BoxCoordinates.EDGES,
            score,
        )
        pixel = PixelBox(record, xyxy, ("Outside image",) if index == 2 else ())
        boxes.append(AssociatedBox("truth", origin, pixel, xyxy))
    catalog = AnnotationCatalog(
        AnnotationFormat.COCO,
        (asset,),
        (
            AnnotationImage("11", "one.png"),
            AnnotationImage("12", "missing.png", label_status="Missing"),
            AnnotationImage("13", "empty.png"),
        ),
        tuple(box.box.record for box in boxes),
    )
    images = (
        AssociatedImage(catalog.images[0], "Ready"),
        AssociatedImage(catalog.images[1], "Ready"),
        AssociatedImage(catalog.images[2], "Ambiguous", (0, 1)),
    )
    source = AssociatedSource(
        AnnotationSource("truth", "annotations.json"),
        catalog,
        images,
        tuple(boxes),
        (AnnotationIssue(asset.path, "annotation[4]", "Invalid geometry"),),
    )
    failed = AssociatedSource(
        AnnotationSource("bad", "missing.json"), None, error="Missing source"
    )
    return PreparedAnnotations(
        "file", "records", revision, "image", (source, failed), {origin: tuple(boxes)}
    )


def test_exact_profiles_separate_classes_original_sizes_and_missing_labels() -> None:
    result = prepare_profiles(prepared(), 8, Event(), ImageProgress())
    profile = result.sources[0]
    assert [(item.id, item.name, item.count) for item in profile.classes] == [
        (7, "person", 2),
        (1, "car", 1),
    ]
    widths, heights, areas, aspects = profile.summaries
    assert (widths.minimum, widths.maximum, widths.mean) == (10.0, 30.0, 50 / 3)
    assert (heights.minimum, heights.maximum, heights.mean) == (10.0, 20.0, 40 / 3)
    assert (areas.minimum, areas.maximum, areas.mean) == (100.0, 300.0, 200.0)
    assert aspects.minimum == 0.5 and aspects.maximum == 3
    assert all(chart.counts.sum() == 3 for chart in profile.distributions)
    assert profile.records["row_id"].to_list() == [7, 7, 7]
    assert profile.records["box_index"].to_list() == [0, 1, 2]
    assert all(item.row_ids == (7,) for item in profile.classes)
    quality = dict(profile.quality)
    assert (
        quality["Missing labels"] == 1 and quality["Present labels without boxes"] == 1
    )
    assert quality["Boxes with warnings"] == 1 and quality["Ambiguous image keys"] == 1
    assert quality["Issues"] == 1
    assert result.sources[1].records.is_empty()
    assert dict(result.sources[1].quality)["Source errors"] == 1
    assert all(chart.counts.sum() == 0 for chart in result.sources[1].distributions)


@pytest.mark.parametrize("orientation", range(1, 9))
def test_overlay_edges_follow_orientation_zoom_pan_and_pick(orientation: int) -> None:
    box = prepared().sources[0].boxes[0]
    box = replace(box, oriented=oriented_box(box.box, 80, 40, orientation))
    viewport = ImageViewport(2.0, 3.0, 4.0)
    x1, y1, x2, y2 = box.oriented
    assert screen_box(box, viewport, (100.0, 200.0)) == (
        100 + (x1 - 3) * 2,
        200 + (y1 - 4) * 2,
        100 + (x2 - 3) * 2,
        200 + (y2 - 4) * 2,
    )
    assert hits(box, ((x1 + x2) / 2, (y1 + y2) / 2))
    assert not hits(box, (x2 + 1, y2 + 1))
    assert visible(box, ImageViewport(0.5), (100, 100))
    assert not visible(box, ImageViewport(1.0, 1000.0, 1000.0), (100, 100))


def test_overlay_filters_are_source_class_and_score_specific() -> None:
    boxes = prepared().sources[0].boxes
    settings = OverlaySettings(minimum_score=0.5, include_unscored=False)
    assert [settings.includes(box) for box in boxes] == [True, False, False]
    assert replace(settings, include_unscored=True).includes(boxes[1])
    assert not OverlaySettings(sources=()).includes(boxes[0])
    assert OverlaySettings(classes=(OverlayClass("truth", 7),)).includes(boxes[0])
    assert not OverlaySettings(classes=(OverlayClass("truth", "7"),)).includes(boxes[0])
    assert not OverlaySettings(classes=(OverlayClass("other", 7),)).includes(boxes[0])
    with pytest.raises(ValueError):
        OverlaySettings(minimum_score=float("nan")).validate()


def test_profiles_abandon_without_partial_publication() -> None:
    stop = Event()
    stop.set()
    with pytest.raises(CancelledError):
        prepare_profiles(prepared(), 8, stop, ImageProgress())
    with pytest.raises(ValueError):
        prepare_profiles(prepared(), 0, Event(), ImageProgress())


def wait(jobs: AnnotationProfileJobs) -> None:
    deadline = monotonic() + 5
    while jobs.busy and monotonic() < deadline:
        jobs.poll()
        sleep(0.001)
    assert not jobs.busy


def test_profiles_require_explicit_commands_and_retire_on_new_source_results() -> None:
    jobs = AnnotationProfileJobs()
    try:
        source = prepared()
        jobs.bind(source)
        assert not jobs.busy and jobs.active is None
        jobs.request()
        wait(jobs)
        assert jobs.active is not None
        jobs.bind(source)
        assert jobs.active is not None
        jobs.bins = 10
        jobs.bind(source)
        assert jobs.active is None
        jobs.request()
        wait(jobs)
        assert jobs.active is not None and jobs.active.bins == 10
        jobs.bind(replace(source, revision=DatasetRevision(uuid4())))
        assert jobs.active is None
    finally:
        jobs.close()


def test_executing_profiles_cannot_publish_after_retirement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered, release = Event(), Event()

    def controlled(
        annotations: PreparedAnnotations,
        bins: int,
        stop: Event,
        progress: ImageProgress,
    ) -> AnnotationProfiles:
        entered.set()
        assert release.wait(5)
        return prepare_profiles(annotations, bins, stop, progress)

    monkeypatch.setattr(
        "datelier.inspection.annotations.profile_jobs.prepare_profiles", controlled
    )
    with ThreadPoolExecutor(1) as executor:
        jobs = AnnotationProfileJobs(executor)
        try:
            jobs.bind(prepared())
            jobs.request()
            assert entered.wait(5)
            jobs.bind(None)
            release.set()
            wait(jobs)
            assert jobs.active is None
        finally:
            release.set()
            jobs.close()
