"""Explicit prepared-annotation profiles, retired when their source results change."""

from concurrent.futures import Executor, Future
from threading import Event

from datelier.core import JobExecutor
from datelier.inspection.annotations.association import PreparedAnnotations
from datelier.inspection.annotations.profiles.prepare import prepare_profiles
from datelier.inspection.annotations.profiles.types import AnnotationProfiles
from datelier.inspection.images.profiles import ImageProgress


class AnnotationProfileJobs:
    def __init__(self, executor: Executor | None = None) -> None:
        self._jobs = JobExecutor(executor, max_workers=1, name="annotation-profile")
        self.active: AnnotationProfiles | None = None
        self.bins = 32
        self.progress = ImageProgress()
        self.message = "Prepare profiles explicitly after associating sources."
        self._bound: PreparedAnnotations | None = None
        self._stamp: tuple[int, int] | None = None
        self._future: Future[AnnotationProfiles] | None = None
        self._stop = Event()
        self.closed = False

    @property
    def busy(self) -> bool:
        return self._future is not None

    def bind(self, annotations: PreparedAnnotations | None) -> None:
        if self.closed:
            return
        stamp = (id(annotations), self.bins)
        if self._stamp != stamp:
            self.abandon()
            self._bound, self._stamp = annotations, stamp
            self.message = "Annotation inputs changed; prepare profiles again."

    def request(self) -> None:
        if self.closed or self._bound is None:
            raise ValueError("Associate annotations before preparing profiles")
        if self._stamp != (id(self._bound), self.bins):
            raise ValueError("Bind changed profile bins before preparing")
        self.abandon()
        self._stop, self.progress = Event(), ImageProgress()
        self._future = self._jobs.submit(
            prepare_profiles, self._bound, self.bins, self._stop, self.progress
        )
        self.message = "Preparing exact annotation profiles…"

    def poll(self) -> None:
        if self.closed or self._future is None or not self._future.done():
            return
        future, self._future = self._future, None
        try:
            self.active = future.result()
            self.message = (
                "Annotation profiles ready. Counts use associated original boxes."
            )
        except Exception as error:
            self.message = f"Annotation profiling failed: {error}"

    def abandon(self) -> None:
        self._stop.set()
        if self._future is not None:
            self._future.cancel()
        self._future, self.active = None, None

    def close(self) -> None:
        self.closed = True
        self.abandon()
        self._bound = None
        self._jobs.shutdown(wait=False, cancel_futures=True)
