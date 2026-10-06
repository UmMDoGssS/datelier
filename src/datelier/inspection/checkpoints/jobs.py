"""File/revision-owned explicit tensor preparation on shared bounded workers."""

from concurrent.futures import Executor, Future
from threading import Event

from datelier.core.dataset import DatasetRevision
from datelier.core.jobs import JobExecutor
from datelier.inspection.arrays.settings import SliceSettings
from datelier.inspection.checkpoints.slices import (
    PreparedTensorSlice,
    prepare_tensor_slice,
)
from datelier.inspection.checkpoints.types import CheckpointCatalog
from datelier.io.checkpoints.storage import CheckpointStore


class CheckpointJobs:
    def __init__(self, executor: Executor | None = None) -> None:
        self._executor = JobExecutor(
            executor, max_workers=1, name="tensor", priority=-5
        )
        self.catalog: CheckpointCatalog | None = None
        self.revision: DatasetRevision | None = None
        self.store = CheckpointStore()
        self.settings = SliceSettings()
        self.active: PreparedTensorSlice | None = None
        self._future: Future[PreparedTensorSlice] | None = None
        self._stamp: tuple[DatasetRevision, SliceSettings] | None = None
        self._cancel = Event()
        self.closed = False
        self.message = "Choose a tensor and prepare its exact values explicitly."

    @property
    def busy(self) -> bool:
        return self._future is not None

    def bind(self, catalog: CheckpointCatalog, revision: DatasetRevision) -> None:
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
            raise ValueError("Open checkpoint metadata before preparing tensor values")
        settings.validate()
        self.abandon()
        self.settings = settings
        self._cancel = Event()
        self._stamp = (self.revision, settings)
        self._future = self._executor.submit(
            prepare_tensor_slice,
            self.store,
            self.catalog,
            settings,
            self._cancel.is_set,
        )
        self.message = "Preparing the selected CPU tensor window…"

    def poll(self) -> None:
        if self.closed or self._future is None or not self._future.done():
            return
        future, self._future = self._future, None
        if self._stamp != (self.revision, self.settings):
            self.message = "Tensor view changed; obsolete preparation ignored."
            return
        try:
            self.active = future.result()
            self.message = "CPU tensor window ready. Source tensor is unchanged."
        except Exception as error:
            self.message = f"Cannot prepare tensor: {error}. Adjust the view and retry."

    def set_retention(self, limit: int) -> None:
        if limit < 0:
            raise ValueError("Checkpoint retention bytes must be nonnegative")
        self.store.limit = limit
        self._executor.submit(self.store.trim)

    def unbind(self) -> None:
        self.abandon()
        self.active = None
        self.catalog = None
        self.revision = None
        self._release_store()

    def _release_store(self) -> None:
        old = self.store
        old.abandon()
        self._executor.submit(old.close)
        self.store = CheckpointStore(old.limit)

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
        self.store.abandon()
        self.catalog = None
        self.revision = None
        self._executor.submit(self.store.close)
        self._executor.shutdown(wait=False, cancel_futures=False)
