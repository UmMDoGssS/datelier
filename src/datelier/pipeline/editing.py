"""Background editing with revision-bound, atomic pipeline/preview publication."""

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, replace
from enum import StrEnum

from datelier.core.dataset import DatasetRevision
from datelier.inspection import Inspection, prepare_inspection
from datelier.pipeline.history import Pipeline
from datelier.pipeline.operations import Operation


class HistoryAction(StrEnum):
    UNDO = "Undo"
    REDO = "Redo"


@dataclass(frozen=True)
class EditResult:
    pipeline: Pipeline
    inspection: Inspection


class DatasetEditor:
    def __init__(self) -> None:
        self.pipeline: Pipeline | None = None
        self.inspection: Inspection | None = None
        self.message = "Open a dataset to edit it."
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="edit")
        self._future: Future[EditResult] | None = None
        self._base: DatasetRevision | None = None
        self._closed = False

    @property
    def busy(self) -> bool:
        return self._future is not None

    def bind(self, inspection: Inspection) -> None:
        self.abandon()
        self.inspection = inspection
        self.pipeline = Pipeline.start(inspection.dataset)
        self.message = "Ready to edit."

    def request(self, action: Operation | HistoryAction) -> None:
        if (
            self._closed
            or self.busy
            or self.pipeline is None
            or self.inspection is None
        ):
            raise ValueError("Editing requires an idle editor and an open dataset")
        pipeline, imported = self.pipeline, self.inspection.imported
        self._base = pipeline.current.revision

        def work() -> EditResult:
            if action == HistoryAction.UNDO:
                result = pipeline.undo()
            elif action == HistoryAction.REDO:
                result = pipeline.redo()
            else:
                result = pipeline.apply(action)
            inspection = prepare_inspection(replace(imported, dataset=result.current))
            return EditResult(result, inspection)

        self._future = self._executor.submit(work)
        self.message = "Applying edit and preparing preview…"

    def poll(self, revision: DatasetRevision | None) -> Inspection | None:
        future = self._future
        if future is None or not future.done():
            return None
        self._future = None
        if revision != self._base:
            self.message = "Dataset changed; obsolete edit ignored."
            return None
        try:
            result = future.result()
        except Exception as error:
            self.message = f"Edit failed: {error}"
            return None
        self.pipeline, self.inspection = result.pipeline, result.inspection
        self.message = "Edit complete."
        return result.inspection

    def abandon(self) -> None:
        if self._future is not None:
            self._future.cancel()
            self._future = None
            self.message = "Edit abandoned; an executing operation may still finish."

    def close(self) -> None:
        self.abandon()
        self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
