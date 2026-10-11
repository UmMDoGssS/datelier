"""Visible array gallery previews share workers and file-owned retention budgets."""

from collections import OrderedDict
from concurrent.futures import Executor, Future

from datelier.application.media_input import MediaController, MediaInput
from datelier.application.sources.columns import record_mapping
from datelier.core.jobs import JobExecutor
from datelier.inspection.arrays.mapping import ArrayLayout
from datelier.inspection.images.gallery import GalleryImage, prepare_gallery_image
from datelier.inspection.images.types import ImageDisplay, ImageOrigin
from datelier.inspection.records.types import RecordCard
from datelier.inspection.references.jobs import ReferenceJobs


class ArrayGalleryController(MediaController):
    def __init__(self, executor: Executor, references: ReferenceJobs) -> None:
        self._jobs = JobExecutor(
            executor, name="array-preview", max_workers=1, priority=-10
        )
        self.references = references
        self._source: MediaInput | None = None
        self._pending: dict[ImageOrigin, Future[GalleryImage]] = {}
        self.previews: OrderedDict[ImageOrigin, GalleryImage] = OrderedDict()
        self.errors: OrderedDict[ImageOrigin, str] = OrderedDict()
        self.display = ImageDisplay()
        self.scope: object = None
        self.closed = False

    @property
    def retained_bytes(self) -> int:
        return sum(preview.retained_bytes for preview in self.previews.values())

    @property
    def pending(self) -> int:
        return len(self._pending)

    def sync(self, source: MediaInput) -> None:
        if self.closed:
            return
        scope = (
            source.file_id,
            source.view_name,
            source.active.dataset.revision if source.active else None,
            source.references.thumbnail_size,
            source.references.cpu_bytes,
            source.references.gpu_bytes,
            self.display,
        )
        if scope != self.scope:
            self.scope = scope
            self.abandon()
        self._source = source
        for origin, future in tuple(self._pending.items()):
            if not future.done():
                continue
            del self._pending[origin]
            try:
                self.previews[origin] = future.result()
            except Exception as error:
                self.errors[origin] = str(error)
        while len(self.errors) > 256:
            self.errors.popitem(last=False)
        while self.previews and (
            self.retained_bytes > source.references.cpu_bytes // 2
            or len(self.previews) > 24
        ):
            self.previews.popitem(last=False)
        self.references.reserve_retention(self.retained_bytes)

    def supports(self, card: RecordCard) -> bool:
        source = self._source
        mapping = record_mapping(
            source.active if source else None,
            card.primary.name if card.primary else None,
        )
        return mapping is not None and mapping.layout in (
            ArrayLayout.IMAGE,
            ArrayLayout.HEATMAP,
        )

    def get(self, card: RecordCard) -> tuple[GalleryImage | None, str]:
        source = self._source
        active = source.active if source else None
        if self.closed or active is None or source is None or card.primary is None:
            return None, ""
        origin = ImageOrigin(
            source.file_id,
            source.view_name,
            active.dataset.revision,
            card.row_id,
            card.primary.name,
        )
        cached = self.previews.get(origin)
        if cached:
            self.previews.move_to_end(origin)
            return cached, ""
        if origin in self.errors:
            self.errors.move_to_end(origin)
            return None, self.errors[origin]
        mapping = record_mapping(active, card.primary.name)
        catalog = active.imported.array_catalog
        if (
            mapping is not None
            and catalog is not None
            and origin not in self._pending
            and len(self._pending) < 2
        ):
            if (
                not 0 <= card.position < active.row_count
                or int(active.dataset.row_ids[card.position]) != card.row_id
            ):
                return None, "Record changed; refresh its gallery page."
            self._pending[origin] = self._jobs.submit(
                prepare_gallery_image,
                active.dataset,
                source.file_id,
                source.view_name,
                card.primary.name,
                card.position,
                catalog,
                mapping,
                self.display,
                source.references.thumbnail_size,
                source.arrays,
            )
        return None, "Preparing array preview…"

    def abandon(self) -> None:
        for future in self._pending.values():
            future.cancel()
        self._pending.clear()
        self.previews.clear()
        self.errors.clear()
        self.references.reserve_retention(0)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.abandon()
        self._source = None
        self._jobs.shutdown(wait=False, cancel_futures=True)
