"""Revision-bound explicit array preparation on shared bounded workers."""

from concurrent.futures import Executor, Future
from threading import Event

from datelier.core.dataset import DatasetRevision
from datelier.core.jobs import JobExecutor
from datelier.inspection.arrays.slices import (
    PreparedSlice,
    SliceSettings,
    prepare_slice,
)
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.io.arrays import ArrayStore


class ArrayJobs:
    def __init__(
        self, executor: Executor | None = None, *, store: ArrayStore | None = None
    ) -> None:
        self._executor = JobExecutor(executor, max_workers=1, name="array", priority=-5)
        self.catalog: ArrayCatalog | None = None
        self.revision: DatasetRevision | None = None
        self.store = store if store is not None else ArrayStore()
        self._owns_store = store is None
        self.settings = SliceSettings()
        self.active: PreparedSlice | None = None
        self._future: Future[PreparedSlice] | None = None
        self._stamp: tuple[DatasetRevision, SliceSettings] | None = None
        self._cancel = Event()
        self.closed = False
        self.message = "Choose a member and prepare its values explicitly."

    @property
    def busy(self) -> bool:
        return self._future is not None

    def bind(self, catalog: ArrayCatalog, revision: DatasetRevision) -> None:
        if self.closed:
            return
        if (
            self.catalog is not None
            and self.catalog.source != catalog.source
            or self.revision is not None
            and self.revision.dataset_id != revision.dataset_id
        ):
            self.abandon()
            self._release_store()
            self.active = None
        if self.revision != revision:
            self.abandon()
            self.active = None
        self.catalog, self.revision = catalog, revision

    def request(self, settings: SliceSettings) -> None:
        if self.closed or self.catalog is None or self.revision is None:
            raise ValueError("Open array metadata before preparing values")
        settings.validate()
        self.abandon()
        self.settings = settings
        self._cancel = Event()
        self._stamp = (self.revision, settings)
        self._future = self._executor.submit(
            prepare_slice, self.store, self.catalog, settings, self._cancel.is_set
        )
        self.message = "Preparing selected member and exact slice…"

    def unbind(self) -> None:
        self.abandon()
        self.active = None
        self.catalog = None
        self.revision = None
        self._release_store()

    def set_retention(self, limit: int) -> None:
        if limit < 0:
            raise ValueError("Retention bytes must be nonnegative")
        self.store.limit = limit
        self._executor.submit(self.store.trim)

    def _release_store(self) -> None:
        if not self._owns_store:
            return
        old = self.store
        old.abandon()
        if old.temporary_path is not None:
            self._executor.submit(old.close)
        self.store = ArrayStore(retained_bytes=old.limit, directory=old.directory)

    def poll(self) -> None:
        if self.closed or self._future is None or not self._future.done():
            return
        future, self._future = self._future, None
        if self._stamp != (self.revision, self.settings):
            self.message = "Array view changed; obsolete preparation ignored."
            return
        try:
            self.active = future.result()
            self.message = "Slice ready. Raw dtype and values are preserved."
        except Exception as error:
            self.message = f"Cannot prepare array: {error}. Adjust settings and retry."

    def abandon(self) -> None:
        self._cancel.set()
        if self._future is not None:
            self._future.cancel()
        self._future = None
        self._stamp = None

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.abandon()
        self.active = None
        self.catalog = None
        if self._owns_store:
            self.store.abandon()
            if self.store.temporary_path is not None:
                self._executor.submit(self.store.close)
        # Cleanup work must survive ownership closure, including queued cleanup.
        self._executor.shutdown(wait=False, cancel_futures=False)
