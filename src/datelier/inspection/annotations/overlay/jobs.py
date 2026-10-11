"""Latest-only scoped scene preparation on the application's shared workers."""

from concurrent.futures import Executor, Future
from threading import Event

from datelier.core.jobs import JobExecutor
from datelier.inspection.annotations.association import (
    AssociatedBox,
    PreparedAnnotations,
)
from datelier.inspection.annotations.overlay.geometry import OverlaySettings
from datelier.inspection.annotations.overlay.scene import (
    Edges,
    OverlayScene,
    prepare_scene,
)
from datelier.inspection.images.types import ImageOrigin
from datelier.inspection.images.viewport import ImageViewport

type SceneStamp = tuple[
    int, ImageOrigin, Edges, ImageViewport, OverlaySettings, AssociatedBox | None, float
]


class SceneJobs:
    def __init__(self, executor: Executor | None) -> None:
        self._jobs = JobExecutor(
            executor, max_workers=1, name="annotation-scene", priority=-9
        )
        self.active: OverlayScene | None = None
        self.message = ""
        self.prepared_count = 0
        self._bound: PreparedAnnotations | None = None
        self._stamp: SceneStamp | None = None
        self._future: Future[OverlayScene] | None = None
        self._stop = Event()
        self.closed = False

    def bind(self, annotations: PreparedAnnotations | None) -> None:
        if annotations is not self._bound:
            self.abandon()
            self._bound = annotations

    def request(
        self,
        origin: ImageOrigin,
        bounds: Edges,
        viewport: ImageViewport,
        settings: OverlaySettings,
        selected: AssociatedBox | None,
        line_height: float,
    ) -> None:
        prepared = self._bound
        if self.closed or prepared is None or not settings.enabled:
            self.abandon()
            return
        if (origin.file_id, origin.view_name, origin.revision) != (
            prepared.file_id,
            prepared.view_name,
            prepared.revision,
        ):
            self.abandon()
            return
        stamp = (
            id(prepared),
            origin,
            bounds,
            viewport,
            settings,
            selected,
            line_height,
        )
        if stamp == self._stamp:
            return
        self.abandon()
        self._stamp = stamp
        self._stop = Event()
        self._future = self._jobs.submit(
            prepare_scene,
            prepared.by_image.get(origin, ()),
            bounds,
            viewport,
            settings,
            selected,
            line_height,
            self._stop,
        )

    def poll(self) -> None:
        if self.closed or self._future is None or not self._future.done():
            return
        future, self._future = self._future, None
        try:
            self.active = future.result()
            self.prepared_count += 1
            self.message = ""
        except Exception as error:
            self.message = f"Annotation scene failed: {error}"

    def abandon(self) -> None:
        self._stop.set()
        if self._future:
            self._future.cancel()
        self._future, self.active, self._stamp = None, None, None

    def close(self) -> None:
        self.closed = True
        self.abandon()
        self._bound = None
        self._jobs.shutdown(wait=False, cancel_futures=True)
