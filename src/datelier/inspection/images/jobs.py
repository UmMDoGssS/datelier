"""File/view/revision-owned image jobs using the shared prioritized worker pool."""

from concurrent.futures import Executor, Future
from threading import Event

from datelier.core.dataset import Dataset, DatasetRevision
from datelier.core.jobs import JobExecutor
from datelier.inspection.arrays.mapping import ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.images.prepare import channel_display, prepare_window
from datelier.inspection.images.sources import prepare_metadata
from datelier.inspection.images.storage import ImageStore
from datelier.inspection.images.types import (
    ImageDisplay,
    ImageLocator,
    ImageMetadata,
    ImageWindow,
    PreparedImage,
)
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays.storage import ArrayStore


class ImageJobs:
    def __init__(self, executor: Executor | None = None) -> None:
        self._jobs = JobExecutor(
            executor, max_workers=1, name="image-window", priority=-10
        )
        self.store = ImageStore()
        self.cpu_bytes = 16 * 1024 * 1024
        self.metadata: tuple[ImageLocator, ImageMetadata] | None = None
        self.active: PreparedImage | None = None
        self.message = "Choose an image record."
        self.closed = False
        self._context: (
            tuple[str, str, DatasetRevision, ReferenceSettings, int] | None
        ) = None
        self._record: tuple[str, int] | None = None
        self._metadata: Future[tuple[ImageLocator, ImageMetadata]] | None = None
        self._window: Future[PreparedImage] | None = None
        self._requested: tuple[ImageWindow, ImageDisplay, int] | None = None
        self._stop = Event()
        self._reference_index: ReferenceIndex | None = None

    @property
    def busy(self) -> bool:
        return self._metadata is not None or self._window is not None

    def sync(
        self,
        file_id: str,
        view_name: str,
        revision: DatasetRevision | None,
        references: ReferenceSettings,
        index: ReferenceIndex | None,
    ) -> None:
        if self.closed:
            return
        context = (
            (file_id, view_name, revision, references, id(index)) if revision else None
        )
        if self._context != context:
            self.abandon()
            if self._context is not None and (
                context is None
                or self._context[:2] != context[:2]
                or self._context[2].dataset_id != context[2].dataset_id
            ):
                old = self.store
                old.abandon()
                self._jobs.submit(old.cleanup)
                self.store = ImageStore(retained_bytes=old.limit)
            self._context = context
        self._reference_index = index

    def request_record(
        self,
        dataset: Dataset,
        column: str,
        position: int,
        catalog: ArrayCatalog | None = None,
        mapping: ArrayRecordMapping | None = None,
    ) -> None:
        if self.closed or self._context is None:
            return
        if self._record == (column, position):
            return
        self.abandon()
        file_id, view_name, revision, references, _ = self._context
        if revision != dataset.revision:
            return
        self._record = (column, position)
        self.message = "Reading image metadata…"
        self._metadata = self._jobs.submit(
            prepare_metadata,
            dataset,
            file_id,
            view_name,
            column,
            position,
            references,
            self._reference_index,
            catalog,
            mapping,
        )

    def request_window(
        self, window: ImageWindow, display: ImageDisplay, arrays: ArrayStore
    ) -> None:
        if self.closed or self.metadata is None:
            return
        window.validate()
        display.validate()
        requested = (window, display, self.cpu_bytes)
        if requested == self._requested:
            return
        if self._window is not None:
            self._window.cancel()
        self._stop.set()
        self._stop = Event()
        self._requested = requested
        self.active = None
        locator, metadata = self.metadata
        self._window = self._jobs.submit(
            prepare_window,
            locator,
            metadata,
            window,
            channel_display(metadata, display),
            self.store,
            arrays,
            self.cpu_bytes,
            self._stop.is_set,
        )
        self.message = "Preparing original-pixel window…"

    def poll(self) -> None:
        if self.closed:
            return
        if self._metadata is not None and self._metadata.done():
            future, self._metadata = self._metadata, None
            try:
                self.metadata = future.result()
                self.message = "Image metadata ready."
            except Exception as error:
                self.message = (
                    f"Cannot inspect image: {error}. Retry or map another file."
                )
        if self._window is not None and self._window.done():
            future, self._window = self._window, None
            try:
                self.active = future.result()
                self.message = (
                    "Original pixels ready; display settings "
                    "do not change source values."
                )
            except Exception as error:
                self.message = f"Image window failed: {error}. Retry preparation."
                self._requested = None

    def abandon(self) -> None:
        self._stop.set()
        for future in (self._metadata, self._window):
            if future is not None:
                future.cancel()
        self._metadata = self._window = None
        self.metadata = self.active = None
        self._record = self._requested = None

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.abandon()
        self._context = None
        self._reference_index = None
        self.store.abandon()
        self._jobs.submit(self.store.cleanup)
        self._jobs.shutdown(wait=False)
