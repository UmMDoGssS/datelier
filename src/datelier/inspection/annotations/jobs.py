"""Explicit annotation commands on shared workers, owned by file/view/revision."""

from concurrent.futures import Executor, Future
from dataclasses import dataclass, replace
from threading import Event

from datelier.core.dataset import Dataset, DatasetRevision
from datelier.core.jobs import JobExecutor
from datelier.inspection.annotations.association import PreparedAnnotations
from datelier.inspection.annotations.association.prepare import prepare_annotations
from datelier.inspection.annotations.settings import AnnotationSettings
from datelier.inspection.arrays.mapping import ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.images.profiles import ImageProgress
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings


@dataclass(frozen=True)
class AnnotationContext:
    file_id: str
    view_name: str
    revision: DatasetRevision
    settings: AnnotationSettings
    references: ReferenceSettings
    index_identity: int
    catalog_identity: int
    mapping: ArrayRecordMapping | None


class AnnotationJobs:
    def __init__(self, executor: Executor | None = None) -> None:
        self._jobs = JobExecutor(
            executor, max_workers=1, name="annotations", priority=0
        )
        self.settings = AnnotationSettings()
        self.active: PreparedAnnotations | None = None
        self.progress = ImageProgress()
        self.message = "Load/associate annotation sources explicitly."
        self.closed = False
        self._context: AnnotationContext | None = None
        self._dataset: Dataset | None = None
        self._index: ReferenceIndex | None = None
        self._catalog: ArrayCatalog | None = None
        self._future: Future[PreparedAnnotations] | None = None
        self._requested: AnnotationContext | None = None
        self._stop = Event()

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
        catalog: ArrayCatalog | None = None,
        mapping: ArrayRecordMapping | None = None,
    ) -> None:
        if self.closed:
            return
        context = (
            AnnotationContext(
                file_id,
                view_name,
                dataset.revision,
                self.settings,
                references,
                id(index),
                id(catalog),
                mapping,
            )
            if dataset is not None
            else None
        )
        if context != self._context:
            was_busy, was_ready = self.busy, self.active is not None
            self.abandon()
            if was_busy:
                self.message = (
                    "Annotation inputs changed; executing reads are abandoned "
                    "and cannot publish."
                )
            elif was_ready:
                self.message = (
                    "Annotation inputs changed; load/associate sources again."
                )
        self._context, self._dataset = context, dataset
        self._index, self._catalog = index, catalog

    def request(self) -> None:
        if self.closed or self._dataset is None or self._context is None:
            raise ValueError("Open image records before associating annotations")
        self.settings.validate()
        if self.settings != self._context.settings:
            raise ValueError("Bind changed annotation settings before preparing")
        if not self.settings.sources:
            raise ValueError("Add an annotation source before loading")
        self.abandon()
        self._stop = Event()
        self.progress = ImageProgress()
        context = self._context
        self._requested = context
        self._future = self._jobs.submit(
            prepare_annotations,
            self._dataset,
            context.file_id,
            context.view_name,
            self.settings,
            context.references,
            self._index,
            self._stop,
            self.progress,
            self._catalog,
            context.mapping,
        )
        self.message = "Reading and associating annotations…"

    def poll(self) -> None:
        if self.closed or self._future is None or not self._future.done():
            return
        future, self._future = self._future, None
        if self._requested != self._context:
            self.message = "Obsolete annotation preparation ignored."
            return
        try:
            prepared = future.result()
            self.active = prepared
            # Confirmed row pins become the saved recipe without invalidating
            # the result that established them. The GUI adopts these settings.
            self.settings = replace(
                self.settings,
                sources=tuple(source.recipe for source in prepared.sources),
            )
            if self._context is not None:
                self._context = replace(self._context, settings=self.settings)
            self.message = (
                "Annotations ready. Source files and original coordinates "
                "are preserved."
            )
        except Exception as error:
            self.message = f"Annotation preparation failed: {error}. Retry association."
        self._requested = None

    def abandon(self) -> None:
        self._stop.set()
        if self._future is not None:
            self._future.cancel()
        self._future = None
        self._requested = None
        self.active = None

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.abandon()
        self._dataset = self._context = self._index = self._catalog = None
        self._jobs.shutdown(wait=False, cancel_futures=True)
