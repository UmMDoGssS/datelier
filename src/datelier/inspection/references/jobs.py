"""File-owned discovery and visible-preview jobs, with byte-bounded retention."""

from collections import OrderedDict
from concurrent.futures import Executor, Future
from math import isqrt
from pathlib import Path
from threading import Event
from time import monotonic

from datelier.core import DatasetRevision, JobExecutor
from datelier.inspection.references.decode import decode
from datelier.inspection.references.index import (
    IndexProgress,
    ReferenceIndex,
    discover,
    resolve,
)
from datelier.inspection.references.types import (
    AssetIdentity,
    AssetPreview,
    ReferenceSettings,
    Resolution,
)


class ReferenceJobs:
    def __init__(self, executor: Executor | None = None) -> None:
        self._index_jobs = JobExecutor(
            executor, max_workers=1, name="reference-index", priority=10
        )
        self._visible_jobs = JobExecutor(
            executor, max_workers=1, name="reference-preview", priority=-10
        )
        self.settings = ReferenceSettings()
        self.source: Path | None = None
        self.revision: DatasetRevision | None = None
        self.index: ReferenceIndex | None = None
        self.progress = IndexProgress()
        self._stop = Event()
        self._index_future: Future[ReferenceIndex] | None = None
        self._resolutions: OrderedDict[tuple[str, str], tuple[float, Resolution]] = (
            OrderedDict()
        )
        self._pending: dict[tuple[str, str], Future[Resolution]] = {}
        self._decodes: dict[AssetIdentity, Future[AssetPreview]] = {}
        self.previews: OrderedDict[AssetIdentity, AssetPreview] = OrderedDict()
        self.message = ""
        self.closed = False
        self._reserved_bytes = 0
        self._discover_nearby = True

    @property
    def retained_bytes(self) -> int:
        return sum(p.retained_bytes for p in self.previews.values())

    def reserve_retention(self, bytes: int) -> None:
        """Visible array previews borrow part of the same file preview budget."""
        self._reserved_bytes = max(0, min(bytes, self.settings.cpu_bytes))
        while (
            self.previews
            and self.retained_bytes > self.settings.cpu_bytes - self._reserved_bytes
        ):
            self.previews.popitem(last=False)

    @property
    def busy(self) -> bool:
        return bool(self._index_future or self._pending or self._decodes)

    def bind(
        self, source: Path, revision: DatasetRevision, *, discover_nearby: bool = True
    ) -> None:
        if self.closed:
            return
        self._discover_nearby = discover_nearby
        if source != self.source or (
            self.revision is not None
            and self.revision.dataset_id != revision.dataset_id
        ):
            self.previews.clear()
            self.source = source
            self.retry()
        if revision != self.revision:
            self.revision = revision
            self._clear_visible()

    def _clear_visible(self) -> None:
        for future in (*self._pending.values(), *self._decodes.values()):
            future.cancel()
        self._pending.clear()
        self._decodes.clear()
        self._resolutions.clear()

    def configure(self, settings: ReferenceSettings) -> None:
        settings.validate()
        if self.settings != settings:
            reindex = (self.settings.roots, self.settings.extensions) != (
                settings.roots,
                settings.extensions,
            )
            resize = self.settings.thumbnail_size != settings.thumbnail_size
            self.settings = settings
            if reindex:
                self.retry()
            else:
                self._clear_visible()
                if resize:
                    self.previews.clear()
                while self.retained_bytes > settings.cpu_bytes:
                    self.previews.popitem(last=False)

    def unbind(self) -> None:
        self.abandon_index()
        self._clear_visible()
        self.index = None
        self.previews.clear()
        self.source = None
        self.revision = None

    def retry(self) -> None:
        self._stop.set()
        if self._index_future:
            self._index_future.cancel()
        self._clear_visible()
        self.previews.clear()
        self.index = None
        self._stop = Event()
        self.progress = IndexProgress()
        if (
            self.source is not None
            and not self.closed
            and (self._discover_nearby or self.settings.roots)
        ):
            self._index_future = self._index_jobs.submit(
                discover, self.source, self.settings, self._stop, self.progress
            )
            self.message = "Discovering nearby references…"
        else:
            self._index_future = None
            self.index = ReferenceIndex({}, {})
            self.message = "Direct record paths; previews load on demand."

    def abandon_index(self) -> None:
        self._stop.set()
        if self._index_future:
            self._index_future.cancel()
        self._index_future = None
        self.message = (
            "Discovery abandoned; any executing scan is winding down. "
            "Exact paths remain usable."
        )

    def poll(self) -> None:
        if self.closed:
            return
        if self._index_future and self._index_future.done():
            future, self._index_future = self._index_future, None
            try:
                self.index = future.result()
                self.message = (
                    f"{self.progress.count:,} references indexed. "
                    + " ".join(self.index.diagnostics)
                )
                self._clear_visible()
            except Exception as error:
                self.message = f"Discovery failed: {error}. Retry discovery."
        for key, future in tuple(self._pending.items()):
            if future.done():
                del self._pending[key]
                try:
                    result = future.result()
                    self._resolutions[key] = (monotonic(), result)
                    while len(self._resolutions) > 256:
                        self._resolutions.popitem(last=False)
                except Exception as error:
                    self._resolutions[key] = (
                        monotonic(),
                        Resolution(key[1], message=str(error)),
                    )
        for asset, future in tuple(self._decodes.items()):
            if future.done():
                del self._decodes[asset]
                try:
                    preview = future.result()
                    if (
                        preview.retained_bytes
                        <= self.settings.cpu_bytes - self._reserved_bytes
                    ):
                        self.previews[asset] = preview
                    while (
                        self.retained_bytes
                        > self.settings.cpu_bytes - self._reserved_bytes
                        or len(self.previews) > 256
                    ):
                        self.previews.popitem(last=False)
                except Exception as error:
                    self.message = f"Preview failed: {error}"

    def get(
        self, column: str, value: str
    ) -> tuple[Resolution | None, AssetPreview | None]:
        if self.closed or self.source is None:
            return None, None
        key = (column, value)
        cached = self._resolutions.get(key)
        if (
            (cached is None or monotonic() - cached[0] > 2)
            and key not in self._pending
            and len(self._pending) < 8
        ):
            self._pending[key] = self._visible_jobs.submit(
                resolve, self.source, column, value, self.settings, self.index
            )
        resolution = cached[1] if cached else None
        asset = resolution.asset if resolution else None
        preview = self.previews.get(asset) if asset else None
        if preview and asset:
            self.previews.move_to_end(asset)
        elif asset and asset not in self._decodes and len(self._decodes) < 4:
            self._decodes[asset] = self._visible_jobs.submit(
                decode,
                asset,
                min(
                    self.settings.thumbnail_size,
                    max(
                        32, isqrt((self.settings.cpu_bytes - self._reserved_bytes) // 4)
                    ),
                ),
            )
        return resolution, preview

    def close(self) -> None:
        self.closed = True
        self._stop.set()
        self._clear_visible()
        if self._index_future:
            self._index_future.cancel()
        self._index_future = None
        self.index = None
        self.previews.clear()
        self._index_jobs.shutdown(wait=False, cancel_futures=True)
        self._visible_jobs.shutdown(wait=False, cancel_futures=True)
