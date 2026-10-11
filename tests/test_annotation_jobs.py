"""Explicit annotation workers reject obsolete contexts and preserve valid row pins."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep

import polars as pl
import pytest
from PIL import Image

from datelier.core import Dataset, DatasetRevision, SourceReference
from datelier.inspection.annotations.association import PreparedAnnotations
from datelier.inspection.annotations.association.prepare import prepare_annotations
from datelier.inspection.annotations.jobs import AnnotationJobs
from datelier.inspection.annotations.settings import (
    AnnotationSettings,
    AnnotationSource,
    ImageAssociationMapping,
    ImageMatch,
)
from datelier.inspection.annotations.types import AnnotationFormat
from datelier.inspection.arrays import ArrayCatalog, ArrayRecordMapping
from datelier.inspection.images.profiles import ImageProgress
from datelier.inspection.references import ReferenceSettings
from datelier.inspection.references.index import ReferenceIndex


def fixture(root: Path) -> tuple[Dataset, AnnotationSettings]:
    Image.new("RGB", (20, 10)).save(root / "scene.png")
    source = root / "table.csv"
    source.write_text("image\nscene.png\n")
    stat = source.stat()
    dataset = Dataset.from_source(
        pl.DataFrame({"image": ["scene.png"]}),
        SourceReference(source, stat.st_size, stat.st_mtime_ns),
    )
    labels = root / "labels.txt"
    labels.write_text("0 0.5 0.5 1 1\n")
    settings = AnnotationSettings(
        "image",
        (
            AnnotationSource(
                "truth",
                str(labels),
                format=AnnotationFormat.YOLO,
                match=ImageMatch.STEM,
                mappings=(ImageAssociationMapping("labels", 0),),
            ),
        ),
    )
    return dataset, settings


def wait(jobs: AnnotationJobs) -> None:
    deadline = monotonic() + 5
    while jobs.busy and monotonic() < deadline:
        jobs.poll()
        sleep(0.001)
    assert not jobs.busy


def test_binding_and_recipe_confirmation_do_not_start_or_repeat_commands(
    tmp_path: Path,
) -> None:
    dataset, settings = fixture(tmp_path)
    jobs = AnnotationJobs()
    try:
        jobs.settings = settings
        jobs.bind(dataset, "file", "records", ReferenceSettings(), None)
        assert not jobs.busy and jobs.active is None
        jobs.request()
        wait(jobs)
        assert jobs.active is not None and len(jobs.active.sources[0].boxes) == 1
        assert jobs.settings.sources[0].mappings[0].expected_key is not None
        jobs.bind(dataset, "file", "records", ReferenceSettings(), None)
        assert not jobs.busy and jobs.active is not None
        jobs.settings = replace(jobs.settings, column="another")
        jobs.bind(dataset, "file", "records", ReferenceSettings(), None)
        assert jobs.active is None and not jobs.busy
    finally:
        jobs.close()


@pytest.mark.parametrize(
    "change", ["file", "view", "revision", "settings", "references", "close"]
)
def test_executing_annotation_results_cannot_publish_after_context_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    dataset, settings = fixture(tmp_path)
    entered, release = Event(), Event()

    def controlled(
        dataset: Dataset,
        file_id: str,
        view_name: str,
        settings: AnnotationSettings,
        references: ReferenceSettings,
        index: ReferenceIndex | None,
        stop: Event,
        progress: ImageProgress,
        catalog: ArrayCatalog | None = None,
        mapping: ArrayRecordMapping | None = None,
    ) -> PreparedAnnotations:
        entered.set()
        assert release.wait(5)
        return prepare_annotations(
            dataset,
            file_id,
            view_name,
            settings,
            references,
            index,
            stop,
            progress,
            catalog,
            mapping,
        )

    monkeypatch.setattr(
        "datelier.inspection.annotations.jobs.prepare_annotations", controlled
    )
    with ThreadPoolExecutor(1) as executor:
        jobs = AnnotationJobs(executor)
        try:
            jobs.settings = settings
            jobs.bind(dataset, "file", "records", ReferenceSettings(), None)
            jobs.request()
            assert entered.wait(5)
            if change == "close":
                jobs.close()
            else:
                if change == "settings":
                    jobs.settings = replace(settings, sources=())
                if change == "revision":
                    dataset = replace(
                        dataset, revision=DatasetRevision(dataset.revision.dataset_id)
                    )
                jobs.bind(
                    dataset,
                    "other" if change == "file" else "file",
                    "other" if change == "view" else "records",
                    ReferenceSettings(roots=(str(tmp_path),))
                    if change == "references"
                    else ReferenceSettings(),
                    None,
                )
            release.set()
            wait(jobs)
            assert jobs.active is None
        finally:
            release.set()
            jobs.close()


def test_request_requires_bound_current_settings_and_open_owner(tmp_path: Path) -> None:
    dataset, settings = fixture(tmp_path)
    jobs = AnnotationJobs()
    with pytest.raises(ValueError, match="Open"):
        jobs.request()
    jobs.bind(dataset, "f", "v", ReferenceSettings(), None)
    with pytest.raises(ValueError, match="Add"):
        jobs.request()
    jobs.settings = settings
    with pytest.raises(ValueError, match="Bind"):
        jobs.request()
    jobs.close()
    with pytest.raises(ValueError, match="Open"):
        jobs.request()
