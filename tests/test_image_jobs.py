"""Executing image windows cannot publish after revision changes or file closure."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from time import monotonic, sleep

import polars as pl
import pytest
from PIL import Image

from datelier.core.dataset import Dataset, DatasetRevision, SourceReference
from datelier.inspection.images.jobs import ImageJobs
from datelier.inspection.images.prepare import prepare_window
from datelier.inspection.images.storage import ImageStore
from datelier.inspection.images.types import (
    ImageDisplay,
    ImageLocator,
    ImageMetadata,
    ImageWindow,
    PreparedImage,
)
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays import ArrayStore


def wait(jobs: ImageJobs) -> None:
    deadline = monotonic() + 5
    while jobs.busy and monotonic() < deadline:
        jobs.poll()
        sleep(0.001)
    assert not jobs.busy


@pytest.mark.parametrize("close", [False, True])
def test_executing_window_is_retired_on_revision_or_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, close: bool
) -> None:
    path = tmp_path / "source.csv"
    path.write_text("image\npicture.png\n")
    Image.new("RGB", (200, 100), (1, 2, 3)).save(tmp_path / "picture.png")
    stat = path.stat()
    dataset = Dataset.from_source(
        pl.DataFrame({"image": ["picture.png"]}),
        SourceReference(path, stat.st_size, stat.st_mtime_ns),
    )
    entered, release = Event(), Event()

    def controlled(
        locator: ImageLocator,
        metadata: ImageMetadata,
        window: ImageWindow,
        display: ImageDisplay,
        images: ImageStore,
        arrays: ArrayStore,
        cpu_bytes: int,
        stopped: Callable[[], bool] | None,
    ) -> PreparedImage:
        entered.set()
        assert release.wait(5)
        return prepare_window(
            locator, metadata, window, display, images, arrays, cpu_bytes, stopped
        )

    monkeypatch.setattr("datelier.inspection.images.jobs.prepare_window", controlled)
    arrays = ArrayStore()
    with ThreadPoolExecutor(1) as worker:
        jobs = ImageJobs(worker)
        try:
            jobs.sync("file", "records", dataset.revision, ReferenceSettings(), None)
            jobs.request_record(dataset, "image", 0)
            wait(jobs)
            jobs.request_window(ImageWindow(), ImageDisplay(), arrays)
            assert entered.wait(5)
            if close:
                jobs.close()
            else:
                jobs.sync(
                    "file",
                    "records",
                    DatasetRevision(dataset.revision.dataset_id),
                    ReferenceSettings(),
                    None,
                )
            release.set()
            wait(jobs)
            assert jobs.active is None and jobs.metadata is None
        finally:
            release.set()
            jobs.close()
    arrays.close()
    assert jobs.store.temporary_path is None
