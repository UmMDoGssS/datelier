"""File/view/revision-owned lazy audio metadata and exact-window workers."""

from concurrent.futures import Executor, Future
from threading import Event

from datelier.core.dataset import Dataset, DatasetRevision
from datelier.core.jobs import JobExecutor
from datelier.inspection.arrays.mapping import ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.audio.reading import prepare_window
from datelier.inspection.audio.sources import prepare_metadata
from datelier.inspection.audio.types import (
    AudioLocator,
    AudioMetadata,
    AudioRange,
    PreparedAudio,
    validate_sample_rate,
)
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays.storage import ArrayStore


class AudioJobs:
    def __init__(self, executor: Executor | None = None) -> None:
        self._jobs = JobExecutor(
            executor, max_workers=1, name="audio-window", priority=-10
        )
        self.metadata: tuple[AudioLocator, AudioMetadata] | None = None
        self.active: PreparedAudio | None = None
        self.message = "Choose an audio record."
        self.closed = False
        self.cpu_bytes = 16 * 1024 * 1024
        self._context: (
            tuple[str, str, DatasetRevision, ReferenceSettings, int] | None
        ) = None
        self._index: ReferenceIndex | None = None
        self._record: tuple[str, int, int | None, ArrayRecordMapping | None] | None = (
            None
        )
        self._metadata: Future[tuple[AudioLocator, AudioMetadata]] | None = None
        self._window: Future[PreparedAudio] | None = None
        self._requested: tuple[AudioRange, int] | None = None
        self._stop = Event()

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
            self._context = context
        self._index = index

    def request_record(
        self,
        dataset: Dataset,
        column: str,
        position: int,
        catalog: ArrayCatalog | None = None,
        mapping: ArrayRecordMapping | None = None,
        array_sample_rate: int | None = None,
    ) -> None:
        if self.closed or self._context is None:
            return
        validate_sample_rate(array_sample_rate)
        requested = (column, position, array_sample_rate, mapping)
        if self._record == requested:
            return
        self.abandon()
        file_id, view_name, revision, references, _ = self._context
        if revision != dataset.revision:
            return
        self._record = requested
        self._metadata = self._jobs.submit(
            prepare_metadata,
            dataset,
            file_id,
            view_name,
            column,
            position,
            references,
            self._index,
            catalog,
            mapping,
            array_sample_rate,
        )
        self.message = "Reading audio metadata…"

    def request_window(self, selected: AudioRange, arrays: ArrayStore) -> None:
        if self.closed or self.metadata is None:
            return
        selected.bounds(self.metadata[1].frames)
        requested = (selected, self.cpu_bytes)
        if self._requested == requested:
            return
        if self._window is not None:
            self._window.cancel()
        self._stop.set()
        self._stop = Event()
        self._requested = requested
        self.active = None
        self._window = self._jobs.submit(
            prepare_window,
            *self.metadata,
            selected,
            arrays,
            self.cpu_bytes,
            self._stop.is_set,
        )
        self.message = "Preparing original audio samples…"

    def poll(self) -> None:
        if self.closed:
            return
        if self._metadata is not None and self._metadata.done():
            future, self._metadata = self._metadata, None
            try:
                self.metadata = future.result()
                self.message = "Audio metadata ready."
            except Exception as error:
                self.message = (
                    f"Cannot inspect audio: {error}. Retry or map another file."
                )
        if self._window is not None and self._window.done():
            future, self._window = self._window, None
            try:
                self.active = future.result()
                self.message = "Original signal window ready; no resampling."
            except Exception as error:
                self.message = f"Audio window failed: {error}. Retry preparation."
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
        self._index = None
        self._jobs.shutdown(wait=False, cancel_futures=True)
