"""Bounded background loading with request/revision-aware publication."""

from collections.abc import Callable
from concurrent.futures import Executor, Future
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from datelier.core import DatasetRevision, JobExecutor
from datelier.inspection.table import Inspection, prepare_inspection
from datelier.io.importing import load_inspectable_file
from datelier.io.types import ImportFormat, ImportOptions, ImportResult


class LoadPhase(StrEnum):
    IDLE = "Ready to open a dataset"
    LOADING = "Loading dataset and preparing preview"
    READY = "Import complete"
    FAILED = "Import failed"
    ABANDONED = "Load abandoned"


@dataclass(frozen=True)
class LoadStatus:
    phase: LoadPhase = LoadPhase.IDLE
    path: Path | None = None
    message: str = ""


@dataclass(frozen=True)
class LoadRequest:
    number: int
    base_revision: DatasetRevision | None
    future: Future[Inspection]


class DatasetLoader:
    """Call request/poll/abandon on the UI thread; workers own heavy work.

    Two workers allow a new load to bypass one abandoned parser. Queued obsolete
    requests are cancelled; running parsers are safely abandoned, never claimed
    stopped. No source data is changed, and failures retain the last inspection.
    """

    def __init__(
        self,
        importer: Callable[[Path, ImportOptions | None], ImportResult] | None = None,
        *,
        executor: Executor | None = None,
    ) -> None:
        self.active: Inspection | None = None
        self.status = LoadStatus()
        self._importer = importer
        self._executor = JobExecutor(executor, max_workers=2, name="import")
        self._number = 0
        self._request: LoadRequest | None = None
        self._retired: list[Future[Inspection]] = []
        self._closed = False

    @property
    def generation(self) -> int:
        return self._number

    @property
    def revision(self) -> DatasetRevision | None:
        return self.active.dataset.revision if self.active else None

    @property
    def retired_running(self) -> int:
        return sum(not future.done() for future in self._retired)

    def request(
        self,
        path: Path,
        options: ImportOptions | None = None,
        *,
        format: ImportFormat | None = None,
    ) -> None:
        if self._closed:
            raise RuntimeError("Loader is closed")
        self._retire()
        self._number += 1

        def work() -> Inspection:
            imported = (
                self._importer(path, options)
                if self._importer is not None
                else load_inspectable_file(path, options, format=format)
            )
            return prepare_inspection(imported)

        self._request = LoadRequest(
            self._number, self.revision, self._executor.submit(work)
        )
        self.status = LoadStatus(LoadPhase.LOADING, path)

    def poll(self) -> bool:
        """Publish only a completed current request against its original revision."""
        self._retired = [future for future in self._retired if not future.done()]
        request = self._request
        if request is None or not request.future.done():
            return False
        self._request = None
        if request.number != self._number or request.base_revision != self.revision:
            self.status = LoadStatus(
                LoadPhase.ABANDONED, self.status.path, "Dataset changed during load."
            )
            return False
        try:
            inspection = request.future.result()
        except Exception as error:
            # Worker boundary: unexpected library failures also stay out of frames.
            self.status = LoadStatus(LoadPhase.FAILED, self.status.path, str(error))
            return False
        self.active = inspection
        self.status = LoadStatus(LoadPhase.READY, self.status.path)
        return True

    def abandon(self) -> None:
        if self._request is not None:
            self._retire()
            self._number += 1
            self.status = LoadStatus(
                LoadPhase.ABANDONED,
                self.status.path,
                "Result will be ignored; an executing parser may still finish.",
            )

    def _retire(self) -> None:
        if self._request is not None:
            self._request.future.cancel()
            self._retired.append(self._request.future)
            self._request = None
        self._retired = [future for future in self._retired if not future.done()]

    def close(self) -> None:
        self.abandon()
        self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
