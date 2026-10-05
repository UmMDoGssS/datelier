"""Resolve multi-file open requests outside frames, bound to their origin tab."""

from concurrent.futures import Executor, Future
from dataclasses import dataclass
from pathlib import Path

from datelier.core.jobs import JobExecutor
from datelier.io.types import ImportFormat, ImportOptions


def resolve_sources(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    return tuple(dict.fromkeys(path.expanduser().resolve() for path in paths))


@dataclass(frozen=True)
class OpeningRequest:
    owner: str
    future: Future[tuple[Path, ...]]
    format: ImportFormat | None = None
    options: ImportOptions | None = None
    retry: bool = False


class OpeningJobs:
    def __init__(self, executor: Executor) -> None:
        self._executor = JobExecutor(executor, max_workers=1, name="opening")
        self._requests: list[OpeningRequest] = []
        self.message = ""

    @property
    def busy(self) -> bool:
        return bool(self._requests)

    def request(
        self,
        paths: tuple[Path, ...],
        owner: str,
        *,
        format: ImportFormat | None = None,
        options: ImportOptions | None = None,
        retry: bool = False,
    ) -> None:
        if not paths:
            raise ValueError("Choose at least one file")
        self._requests.append(
            OpeningRequest(
                owner,
                self._executor.submit(resolve_sources, paths),
                format,
                options,
                retry,
            )
        )
        self.message = "Resolving chosen source paths…"

    def poll(
        self, owners: set[str]
    ) -> tuple[tuple[OpeningRequest, tuple[Path, ...]], ...]:
        ready: list[tuple[OpeningRequest, tuple[Path, ...]]] = []
        for request in tuple(self._requests):
            if request.owner not in owners:
                request.future.cancel()
                self._requests.remove(request)
                self.message = "Opening abandoned because its tab was closed."
            elif request.future.done():
                self._requests.remove(request)
                try:
                    ready.append((request, request.future.result()))
                    self.message = "Chosen files queued in independent tabs."
                except Exception as error:
                    self.message = (
                        f"Could not resolve chosen files: {error}. Choose another path."
                    )
        return tuple(ready)

    def close(self) -> None:
        self._requests.clear()
        self._executor.shutdown(wait=False, cancel_futures=True)
