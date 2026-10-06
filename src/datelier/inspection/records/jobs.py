"""File/view-owned record preparation and small virtual gallery pages."""

from collections import OrderedDict
from concurrent.futures import Executor, Future
from dataclasses import replace

from datelier.core.dataset import Dataset, DatasetRevision
from datelier.core.jobs import JobExecutor
from datelier.inspection.records.prepare import (
    RECORD_PAGE_SIZE,
    prepare_record_page,
    prepare_records,
)
from datelier.inspection.records.types import (
    InspectSettings,
    RecordMode,
    RecordPage,
    RecordSet,
)


class RecordJobs:
    def __init__(self, executor: Executor | None = None) -> None:
        self._executor = JobExecutor(
            executor, max_workers=1, name="records", priority=-5
        )
        self._stamp: tuple[DatasetRevision, InspectSettings, tuple[int, ...]] | None = (
            None
        )
        self._dataset: Dataset | None = None
        self._future: Future[RecordSet] | None = None
        self._pages: OrderedDict[int, RecordPage] = OrderedDict()
        self._pending: dict[int, Future[RecordPage]] = {}
        self.active: RecordSet | None = None
        self.message = "Open a source to inspect records."
        self.closed = False

    def sync(
        self, dataset: Dataset, settings: InspectSettings, selection: tuple[int, ...]
    ) -> None:
        if self.closed:
            return
        chosen = selection if settings.mode == RecordMode.SELECTION else ()
        # Gallery/focus are presentation only and do not rebuild the collection.
        prepared_settings = replace(settings, gallery=True, focus=0)
        stamp = (dataset.revision, prepared_settings, chosen)
        if self._stamp != stamp:
            self.abandon()
            self._dataset = dataset
            self._stamp = stamp
            self._future = self._executor.submit(
                prepare_records, dataset, prepared_settings, chosen
            )
            self.message = "Preparing record identities…"

    def poll(self) -> None:
        if self.closed:
            return
        if self._future and self._future.done():
            future, self._future = self._future, None
            try:
                self.active = future.result()
                self.message = (
                    f"{self.active.settings.mode}: "
                    f"{len(self.active.positions):,} records from "
                    f"{self.active.eligible:,} current rows."
                )
                if self.active.settings.mode == RecordMode.RANDOM:
                    self.message += f" Seed {self.active.settings.seed}."
            except Exception as error:
                self.message = (
                    f"Cannot prepare Inspect: {error}. Change settings and retry."
                )
        for start, future in tuple(self._pending.items()):
            if future.done():
                del self._pending[start]
                try:
                    page = future.result()
                    if self._dataset and page.revision == self._dataset.revision:
                        self._pages[start] = page
                        while len(self._pages) > 4:
                            self._pages.popitem(last=False)
                except Exception as error:
                    self.message = (
                        f"Cannot prepare record page: {error}. Retry Inspect."
                    )

    def get(self, slot: int) -> RecordPage | None:
        if self.closed or self.active is None or self._dataset is None:
            return None
        start = slot // RECORD_PAGE_SIZE * RECORD_PAGE_SIZE
        page = self._pages.get(start)
        if page:
            self._pages.move_to_end(start)
        elif start not in self._pending and len(self._pending) < 2:
            self._pending[start] = self._executor.submit(
                prepare_record_page, self._dataset, self.active, start
            )
        return page

    def abandon(self) -> None:
        if self._future:
            self._future.cancel()
        for future in self._pending.values():
            future.cancel()
        self._future = None
        self._pending.clear()
        self._pages.clear()
        self._stamp = None
        self._dataset = None
        self.active = None

    def close(self) -> None:
        self.closed = True
        self.abandon()
        self._executor.shutdown(wait=False, cancel_futures=True)
