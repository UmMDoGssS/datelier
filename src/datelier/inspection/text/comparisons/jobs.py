"""Explicit commands; changed/closed contributors invalidate without rerunning."""

from concurrent.futures import Executor, Future
from threading import Event

from datelier.core.dataset import Dataset
from datelier.core.jobs import JobExecutor
from datelier.inspection.comparisons.types import ComparisonSelection
from datelier.inspection.text.comparisons.prepare import (
    prepare_comparison,
    select_length_bin,
)
from datelier.inspection.text.comparisons.settings import TextComparisonSettings
from datelier.inspection.text.comparisons.types import (
    PreparedTextComparison,
    TextComparisonInput,
)
from datelier.inspection.text.corpus import TextProgress
from datelier.inspection.text.types import CorpusMode


class TextComparisonJobs:
    def __init__(self, executor: Executor | None = None) -> None:
        self._executor = JobExecutor(
            executor, max_workers=1, name="text-compare", priority=-4
        )
        self._stamp: tuple[object, ...] = ()
        self._recipe: TextComparisonSettings | None = None
        self._inputs: tuple[TextComparisonInput, ...] = ()
        self._future: Future[PreparedTextComparison] | None = None
        self._selection: Future[ComparisonSelection] | None = None
        self._selection_result: PreparedTextComparison | None = None
        self._stop = Event()
        self.progress = TextProgress()
        self.active: PreparedTextComparison | None = None
        self.message = "Map two or more text fields and prepare a comparison."
        self.selection_message = ""
        self.started = 0
        self.closed = False

    @property
    def busy(self) -> bool:
        return self._future is not None

    def bind(
        self,
        recipe: TextComparisonSettings | None,
        inputs: tuple[TextComparisonInput, ...],
    ) -> None:
        if self.closed:
            return
        stamp = (
            recipe,
            *(
                (
                    i.source.file_id,
                    i.dataset.revision,
                    i.view_name,
                    i.references,
                    id(i.index),
                    i.selection if i.source.scope.mode == CorpusMode.SELECTION else (),
                )
                for i in inputs
            ),
        )
        if stamp != self._stamp:
            self.clear()
            self._stamp, self._recipe, self._inputs = stamp, recipe, inputs
            self.message = "Text comparison inputs changed; prepare explicitly."

    def poll(self) -> None:
        if self._future is not None and self._future.done():
            future, self._future = self._future, None
            try:
                self.active = future.result()
                self.message = "Shared-tokenizer text comparison ready."
            except Exception as error:
                self.message = str(error)

    def request(self) -> None:
        if self.closed or self._recipe is None:
            raise ValueError("Choose a text comparison")
        self._recipe.validate()
        if (
            len(self._recipe.sources) < 2
            or tuple(i.source for i in self._inputs) != self._recipe.sources
        ):
            raise ValueError(
                "Map two available text sources; recover missing files first"
            )
        self.clear()
        self._future = self._executor.submit(
            prepare_comparison, self._inputs, self._recipe, self._stop, self.progress
        )
        self.started += 1
        self.message = "Preparing complete mapped text corpora with one tokenizer…"

    def request_selection(
        self,
        result: PreparedTextComparison,
        series: int,
        bin_index: int,
        dataset: Dataset,
    ) -> None:
        if self.closed or self.active is not result:
            raise ValueError("The comparison changed; prepare a current result")
        if self._selection is not None:
            self._selection.cancel()
        self._selection_result = result
        self._selection = self._executor.submit(
            select_length_bin, result, series, bin_index, dataset
        )
        self.selection_message = "Selecting matching rows in the mapped text source…"

    def poll_selection(
        self, datasets: dict[str, Dataset]
    ) -> ComparisonSelection | None:
        if self._selection is None or not self._selection.done():
            return None
        future, self._selection = self._selection, None
        try:
            selection = future.result()
            dataset = datasets.get(selection.origin.file_id)
            if (
                self._selection_result is not self.active
                or dataset is None
                or dataset.revision != selection.origin.revision
            ):
                raise ValueError(
                    "Mapped text source changed or closed; obsolete selection ignored"
                )
            self.selection_message = (
                f"{len(selection.row_ids):,} of {selection.matches:,} "
                "matching source rows selected."
            )
            return selection
        except Exception as error:
            self.selection_message = str(error)
            return None
        finally:
            self._selection_result = None

    def clear(self) -> None:
        self._stop.set()
        for future in (self._future, self._selection):
            if future is not None:
                future.cancel()
        self._future = self._selection = None
        self._selection_result = None
        self._stop = Event()
        self.active = None

    def close(self) -> None:
        self.clear()
        self._inputs = ()
        self._recipe = None
        self.closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
