"""Explicit mapped-record slices with stable source identity and shared storage."""

from concurrent.futures import Executor
from dataclasses import replace

from datelier.application.media_input import MediaInput
from datelier.application.sources.columns import record_mapping
from datelier.inspection.arrays.jobs import ArrayJobs
from datelier.inspection.arrays.mapping import ArrayRecordMapping
from datelier.io.arrays import ArrayStore
from datelier.io.types import ArrayOptions


class ArrayRecordController:
    def __init__(self, executor: Executor, store: ArrayStore) -> None:
        self.jobs = ArrayJobs(executor, store=store)
        self.source: MediaInput | None = None
        self.mapping: ArrayRecordMapping | None = None
        self.channel = 0
        self._stamp: tuple[str, int, int] | None = None

    def sync(self, source: MediaInput) -> None:
        self.source = source
        active = source.active
        if self.jobs.store is not source.arrays or self.jobs.revision != (
            active.dataset.revision if active else None
        ):
            self.jobs.store = source.arrays
            self._stamp = None
        if active and active.imported.array_catalog:
            self.jobs.bind(active.imported.array_catalog, active.dataset.revision)
        else:
            self.jobs.unbind()
        self.jobs.poll()

    def bind_record(self, column: str, row_id: int) -> None:
        active = self.source.active if self.source else None
        if active is None or not isinstance(active.imported.options, ArrayOptions):
            return
        catalog = active.imported.array_catalog
        mapping = record_mapping(active, column)
        if catalog is None or mapping is None:
            return
        self.mapping = mapping
        stamp = (column, row_id, self.channel)
        if stamp != self._stamp:
            self.jobs.active = None
            self.jobs.abandon()
            try:
                configured = mapping.slice_settings(
                    catalog, row_id, channel=self.channel
                )
            except ValueError as error:
                self.jobs.message = str(error)
                return
            previous = self.jobs.settings
            if (
                configured.member == previous.member
                and configured.axes == previous.axes
            ):
                configured = replace(
                    configured,
                    starts=previous.starts,
                    counts=previous.counts,
                    field=previous.field,
                    component=previous.component,
                    value_range=previous.value_range,
                    colormap=previous.colormap,
                )
            self.jobs.settings = configured
            self.jobs.active = None
            self.jobs.abandon()
            self._stamp = stamp

    def close(self) -> None:
        self.source = None
        self.mapping = None
        self.jobs.close()
