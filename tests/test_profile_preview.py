from pathlib import Path
from threading import Event
from time import monotonic, sleep

import polars as pl

from datelier.core.dataset import Dataset, SourceReference
from datelier.distributions import DistributionSettings
from datelier.profile_preview import ProfileGroup, ProfilePreview, ProfileRequest


def data(offset: int = 0) -> Dataset:
    return Dataset.from_source(
        pl.DataFrame({"x": [offset + 1.0, offset + 2.0, offset + 3.0]}),
        SourceReference(Path("unused"), 0, 0),
    )


def wait(preview: ProfilePreview, dataset: Dataset) -> None:
    deadline = monotonic() + 3
    while preview.busy and monotonic() < deadline:
        preview.poll(dataset.revision)
        sleep(0.001)
    assert not preview.busy


def test_reuse_error_recovery_revision_and_close() -> None:
    dataset = data()
    request = ProfileRequest(DistributionSettings(("x",)))
    preview = ProfilePreview()
    try:
        preview.ensure(dataset, request)
        wait(preview, dataset)
        active = preview.active
        assert active and active.profiles.columns[0].statistics
        preview.ensure(dataset, request)
        assert not preview.busy and preview.active is active
        preview.ensure(dataset, ProfileRequest(DistributionSettings(("gone",))))
        wait(preview, dataset)
        assert preview.active is None and "unavailable" in preview.message.lower()
        preview.ensure(dataset, request)
        wait(preview, dataset)
        assert preview.active is not None
        preview.poll(data(5).revision)
        assert preview.active is None
    finally:
        preview.close()
    preview.ensure(dataset, request)
    assert not preview.busy


def test_running_old_selection_and_abandon_cannot_publish(monkeypatch) -> None:
    import datelier.profile_preview as module

    old, new = data(), data(10)
    started, release = Event(), Event()
    original = module.prepare_profile_group

    def slow(dataset: Dataset, request: ProfileRequest) -> ProfileGroup:
        if dataset is old:
            started.set()
            assert release.wait(3)
        return original(dataset, request)

    monkeypatch.setattr(module, "prepare_profile_group", slow)
    request = ProfileRequest(DistributionSettings(("x",)))
    preview = ProfilePreview()
    try:
        preview.ensure(old, request)
        assert started.wait(3)
        preview.ensure(new, request)
        release.set()
        wait(preview, new)
        assert preview.active and preview.active.profiles.revision == new.revision
        stats = preview.active.profiles.columns[0].statistics
        assert stats and stats.mean == 12
        preview.ensure(old, request)
        preview.clear()
        preview.poll(old.revision)
        assert preview.active is None and not preview.busy
    finally:
        release.set()
        preview.close()
