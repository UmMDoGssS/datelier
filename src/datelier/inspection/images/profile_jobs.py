"""Explicit image profile jobs scoped to file/view, revision, settings and selection."""

from concurrent.futures import Executor, Future
from threading import Event

from datelier.core.dataset import Dataset, DatasetRevision
from datelier.core.jobs import JobExecutor
from datelier.inspection.arrays.mapping import ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.images.profile_types import (
    ImageProfile,
    ImageProfileSettings,
    ImageProgress,
    ImageScopeMode,
)
from datelier.inspection.images.profiles import prepare_image_profile
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays.storage import ArrayStore


class ImageProfileJobs:
    def __init__(self, executor: Executor | None = None) -> None:
        self._jobs = JobExecutor(
            executor, max_workers=1, name="image-profile", priority=5
        )
        self.settings = ImageProfileSettings()
        self.active: ImageProfile | None = None
        self.progress = ImageProgress()
        self.message = "Prepare image collection statistics explicitly."
        self.closed = False
        self._future: Future[ImageProfile] | None = None
        self._stop = Event()
        self._stamp: (
            tuple[
                str,
                str,
                DatasetRevision,
                ImageProfileSettings,
                ReferenceSettings,
                tuple[int, ...],
                ArrayRecordMapping | None,
            ]
            | None
        ) = None
        self._dataset: Dataset | None = None
        self._index: ReferenceIndex | None = None
        self._catalog: ArrayCatalog | None = None
        self._arrays: ArrayStore | None = None

    @property
    def busy(self) -> bool:
        return self._future is not None

    def bind(
        self,
        dataset: Dataset | None,
        file_id: str,
        view_name: str,
        references: ReferenceSettings,
        index: ReferenceIndex | None,
        selection: tuple[int, ...],
        arrays: ArrayStore,
        catalog: ArrayCatalog | None = None,
        mapping: ArrayRecordMapping | None = None,
    ) -> None:
        if self.closed:
            return
        chosen = (
            selection if self.settings.scope.mode == ImageScopeMode.SELECTION else ()
        )
        stamp = (
            (
                file_id,
                view_name,
                dataset.revision,
                self.settings,
                references,
                chosen,
                mapping,
            )
            if dataset
            else None
        )
        if stamp != self._stamp or index is not self._index:
            was_busy = self.busy
            was_prepared = self.active is not None
            self.abandon()
            if was_busy:
                self.message = (
                    "Image inputs changed; executing profiling is abandoned "
                    "and cannot publish."
                )
            elif was_prepared:
                self.message = (
                    "Image inputs changed; prepare collection statistics again."
                )
        self._stamp, self._dataset = stamp, dataset
        self._index, self._catalog, self._arrays = index, catalog, arrays

    def request(self) -> None:
        if (
            self.closed
            or self._dataset is None
            or self._stamp is None
            or self._arrays is None
        ):
            raise ValueError(
                "Open an image source before preparing collection statistics"
            )
        self.settings.validate()
        if self._stamp[3] != self.settings:
            raise ValueError("Bind changed image settings before profiling")
        self.abandon()
        self._stop = Event()
        self.progress = ImageProgress()
        file_id, view_name, _, _, references, selection, mapping = self._stamp
        self._future = self._jobs.submit(
            prepare_image_profile,
            self._dataset,
            file_id,
            view_name,
            self.settings,
            selection,
            references,
            self._index,
            self._arrays,
            self._stop,
            self.progress,
            self._catalog,
            mapping,
        )
        self.message = "Preparing image collection statistics…"

    def poll(self) -> None:
        if self.closed or self._future is None or not self._future.done():
            return
        future, self._future = self._future, None
        try:
            self.active = future.result()
            profile = self.active
            kind = "Sampled pixels" if profile.sampled_pixels else "All original pixels"
            self.message = (
                f"{kind}: {profile.ready:,} decoded images; {profile.nulls:,} null, "
                f"{profile.unresolved:,} unresolved, "
                f"{profile.failures:,} failed records."
            )
        except Exception as error:
            self.message = (
                f"Image profiling failed: {error}. Retry collection statistics."
            )

    def abandon(self) -> None:
        self._stop.set()
        if self._future is not None:
            self._future.cancel()
        self._future = None
        self.active = None

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.abandon()
        self._dataset = self._catalog = self._arrays = None
        self._index = self._stamp = None
        self._jobs.shutdown(wait=False, cancel_futures=True)
