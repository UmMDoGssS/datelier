"""Image profiles require an explicit command and retire on scope/owner changes."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep

import polars as pl
import pytest
from PIL import Image

from datelier.core import Dataset, DatasetRevision, SourceReference
from datelier.inspection.images.profiles import (
    ImageProfile,
    ImageProfileSettings,
    ImageScope,
    ImageScopeMode,
)
from datelier.inspection.images.profiles.jobs import ImageProfileJobs
from datelier.inspection.references import ReferenceSettings
from datelier.io.arrays import ArrayStore


def dataset(root: Path) -> Dataset:
    source = root / "images.csv"
    source.write_text("image\nimage.png\n")
    Image.new("L", (2, 3), 20).save(root / "image.png")
    stat = source.stat()
    return Dataset.from_source(
        pl.DataFrame({"image": ["image.png"]}),
        SourceReference(source, stat.st_size, stat.st_mtime_ns),
    )


def wait(jobs: ImageProfileJobs) -> None:
    end = monotonic() + 5
    while jobs.busy and monotonic() < end:
        jobs.poll()
        sleep(0.001)
    assert not jobs.busy


def test_profile_commands_are_explicit_and_settings_invalidate_results(
    tmp_path: Path,
) -> None:
    table, arrays, jobs = dataset(tmp_path), ArrayStore(), ImageProfileJobs()
    try:
        jobs.settings = ImageProfileSettings("image")
        jobs.bind(table, "file", "records", ReferenceSettings(), None, (), arrays)
        assert not jobs.busy and jobs.active is None and arrays.temporary_path is None
        jobs.request()
        wait(jobs)
        assert jobs.active is not None and jobs.active.summaries[0].mean == 20
        jobs.settings = replace(jobs.settings, bins=4)
        jobs.bind(table, "file", "records", ReferenceSettings(), None, (), arrays)
        assert jobs.active is None and not jobs.busy
        assert "changed" in jobs.message
        jobs.request()
        wait(jobs)
        assert jobs.active is not None and len(jobs.active.channels[0].counts) == 4
    finally:
        jobs.close()
        arrays.close()


@pytest.mark.parametrize("change", ["revision", "view", "file", "selection", "close"])
def test_executing_profiles_cannot_publish_into_another_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    table, arrays = dataset(tmp_path), ArrayStore()
    entered, release = Event(), Event()
    from datelier.inspection.images.profiles.prepare import prepare_image_profile

    def delayed(*args, **kwargs) -> ImageProfile:
        entered.set()
        assert release.wait(5)
        return prepare_image_profile(*args, **kwargs)

    monkeypatch.setattr(
        "datelier.inspection.images.profiles.jobs.prepare_image_profile", delayed
    )
    with ThreadPoolExecutor(1) as worker:
        jobs = ImageProfileJobs(worker)
        try:
            jobs.settings = ImageProfileSettings(
                "image", ImageScope(ImageScopeMode.SELECTION)
            )
            jobs.bind(table, "file", "records", ReferenceSettings(), None, (0,), arrays)
            jobs.request()
            assert entered.wait(5)
            if change == "close":
                jobs.close()
            else:
                if change == "revision":
                    table = replace(
                        table, revision=DatasetRevision(table.revision.dataset_id)
                    )
                jobs.bind(
                    table,
                    "other" if change == "file" else "file",
                    "other" if change == "view" else "records",
                    ReferenceSettings(),
                    None,
                    () if change == "selection" else (0,),
                    arrays,
                )
            release.set()
            wait(jobs)
            assert jobs.active is None and not jobs.busy
        finally:
            release.set()
            jobs.close()
    arrays.close()
