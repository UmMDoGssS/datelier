from pathlib import Path
from threading import Event
from time import monotonic, sleep

import polars as pl

from datelier.core import Dataset, SourceReference
from datelier.plotting.distributions import Comparison, DistributionSettings
from datelier.plotting.distributions.preview import DistributionPreview


def dataset(values: list[float]) -> Dataset:
    return Dataset.from_source(
        pl.DataFrame({"x": values}), SourceReference(Path("unused"), 0, 0)
    )


def wait(preview: DistributionPreview, data: Dataset) -> None:
    deadline = monotonic() + 3
    while preview.busy and monotonic() < deadline:
        preview.poll(data.revision)
        sleep(0.001)
    assert not preview.busy


def test_reuse_failure_recovery_and_revision_invalidation() -> None:
    data = dataset([1, 2, 2, 4])
    settings = DistributionSettings(("x",))
    preview = DistributionPreview()
    try:
        preview.ensure(data, settings, 2)
        wait(preview, data)
        result = preview.active
        assert result is not None and result.series[0].ecdf_y.tolist() == [
            0.25,
            0.75,
            1,
        ]
        preview.ensure(data, settings, 2)
        assert not preview.busy and preview.active is result
        preview.ensure(data, DistributionSettings(("missing",)), 2)
        wait(preview, data)
        assert preview.active is None and "unavailable" in preview.message.lower()
        preview.ensure(data, settings, 3)
        wait(preview, data)
        assert preview.active is not None
        preview.poll(data.with_rows(data.table, data.row_ids).revision)
        assert preview.active is None
    finally:
        preview.close()


def test_obsolete_and_abandoned_preparation_cannot_publish(monkeypatch) -> None:
    import datelier.plotting.distributions.preview as module

    old, new = dataset([1, 2, 3]), dataset([5, 6, 7])
    original = module.prepare_comparison
    started, release = Event(), Event()

    def slow(data: Dataset, settings: DistributionSettings, bins: int) -> Comparison:
        if data is old:
            started.set()
            assert release.wait(3)
        return original(data, settings, bins)

    monkeypatch.setattr(module, "prepare_comparison", slow)
    preview = DistributionPreview()
    settings = DistributionSettings(("x",))
    try:
        preview.ensure(old, settings, 2)
        assert started.wait(3)
        preview.ensure(new, settings, 2)
        release.set()
        wait(preview, new)
        assert preview.active is not None
        assert preview.active.series[0].ecdf_x.tolist() == [5, 6, 7]
        preview.ensure(old, settings, 2)
        preview.clear()
        preview.poll(old.revision)
        assert preview.active is None and not preview.busy
    finally:
        release.set()
        preview.close()
