"""Shared bounded workers with independently closable job ownership."""

from collections.abc import Callable
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from threading import Condition
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


class SharedWorkers(Executor):
    """One application pool; saturation produces a retryable worker failure."""

    def __init__(self, *, workers: int = 4, capacity: int = 64) -> None:
        if workers < 1 or capacity < workers:
            raise ValueError("Worker capacity must cover the positive worker count")
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="file")
        self._condition = Condition()
        self._pending = 0
        self.capacity = capacity
        self._closed = False

    @property
    def pending(self) -> int:
        with self._condition:
            return self._pending

    def submit(
        self, fn: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs
    ) -> Future[T]:
        with self._condition:
            if self._closed:
                raise RuntimeError("Application workers are closed")
            if self._pending >= self.capacity:
                rejected: Future[T] = Future()
                rejected.set_exception(
                    RuntimeError("Workers are busy. Retry when another job finishes.")
                )
                return rejected
            self._pending += 1
        try:
            future = self._pool.submit(fn, *args, **kwargs)
        except RuntimeError:
            self._finished()
            raise
        future.add_done_callback(lambda _: self._finished())
        return future

    def _finished(self) -> None:
        with self._condition:
            self._pending -= 1
            self._condition.notify_all()

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        with self._condition:
            self._closed = True
        self._pool.shutdown(wait=wait, cancel_futures=cancel_futures)


class JobExecutor(Executor):
    """Track one controller's futures without owning an injected shared pool.

    A scope can cancel its queued jobs and await its executing jobs independently.
    Standalone controllers retain their small private pool for CLI/test use.
    """

    def __init__(
        self, executor: Executor | None, *, max_workers: int, name: str
    ) -> None:
        self._owns_pool = executor is None
        self._pool = (
            executor
            if executor is not None
            else ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=name)
        )
        self._condition = Condition()
        self._jobs: dict[int, Callable[[], bool]] = {}
        self._number = 0
        self._closed = False

    def submit(
        self, fn: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs
    ) -> Future[T]:
        with self._condition:
            if self._closed:
                raise RuntimeError("Job owner is closed")
            self._number += 1
            number = self._number
            future = self._pool.submit(fn, *args, **kwargs)
            self._jobs[number] = future.cancel
            future.add_done_callback(lambda _: self._finished(number))
            return future

    def _finished(self, number: int) -> None:
        with self._condition:
            self._jobs.pop(number, None)
            self._condition.notify_all()

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        with self._condition:
            self._closed = True
            if cancel_futures:
                for cancel in tuple(self._jobs.values()):
                    cancel()
            if wait:
                self._condition.wait_for(lambda: not self._jobs)
        if self._owns_pool:
            self._pool.shutdown(wait=wait, cancel_futures=cancel_futures)
