"""Explicit audio collection jobs scoped independently from record inspection."""

from concurrent.futures import Executor, Future
from threading import Event

from datelier.application.media_input import MediaInput
from datelier.application.sources.columns import record_mapping
from datelier.core.jobs import JobExecutor
from datelier.inspection.audio.collections.scan import scan_collection
from datelier.inspection.audio.collections.settings import (
    AudioCollectionSettings,
    AudioScopeMode,
)
from datelier.inspection.audio.collections.types import (
    AudioCollectionProfile,
    CollectionProgress,
)
from datelier.inspection.audio.types import AudioLocator


class AudioCollectionController:
    def __init__(self, executor: Executor | None) -> None:
        self.jobs = JobExecutor(
            executor, max_workers=1, name="audio-collection", priority=5
        )
        self.settings = AudioCollectionSettings()
        self.active: AudioCollectionProfile | None = None
        self.progress = CollectionProgress()
        self.message = (
            "Prepare audio collection headers or exact signal statistics explicitly."
        )
        self._source: MediaInput | None = None
        self._stamp: tuple[object, ...] = ()
        self._future: (
            Future[tuple[AudioCollectionProfile, tuple[AudioLocator, ...]]] | None
        ) = None
        self._stop = Event()

    @property
    def busy(self) -> bool:
        return self._future is not None

    def sync(self, source: MediaInput) -> None:
        active = source.active
        mapping = record_mapping(active, self.settings.column)
        stamp = (
            source.file_id,
            source.view_name,
            active.dataset.revision if active else None,
            self.settings,
            source.references,
            id(source.index),
            source.selected_rows
            if self.settings.scope.mode == AudioScopeMode.SELECTION
            else (),
            mapping,
        )
        if stamp != self._stamp:
            previous = self.busy or self.active is not None
            self.abandon()
            self._stamp = stamp
            if previous:
                self.message = "Audio collection inputs changed; prepare again."
        self._source = source
        if self._future and self._future.done():
            future, self._future = self._future, None
            try:
                self.active, _ = future.result()
                self.message = (
                    f"{self.active.ready:,} ready · {self.active.nulls:,} null · "
                    f"{self.active.failures:,} failed"
                )
            except Exception as error:
                self.message = f"Audio collection failed: {error}"

    def request(self) -> None:
        source = self._source
        if source is None or source.active is None:
            raise ValueError("Open an audio field before preparing a collection")
        self.settings.validate()
        self.abandon()
        self.progress = CollectionProgress()
        self._stop = Event()
        self._future = self.jobs.submit(
            scan_collection,
            source.active.dataset,
            source.file_id,
            source.view_name,
            self.settings,
            source.selected_rows,
            source.references,
            source.index,
            source.arrays,
            self._stop,
            self.progress,
            source.active.imported.array_catalog,
            record_mapping(source.active, self.settings.column),
        )
        self.message = "Preparing the chosen audio collection…"

    def abandon(self) -> None:
        self._stop.set()
        if self._future:
            self._future.cancel()
        self._future = None
        self.active = None
        self.message = "Collection work abandoned; executing work cannot publish."

    def close(self) -> None:
        self.abandon()
        self._source = None
        self._stamp = ()
        self.jobs.shutdown(wait=False, cancel_futures=True)
