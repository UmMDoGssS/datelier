"""Only changed contributors invalidate a comparison; obsolete jobs cannot publish."""

from concurrent.futures import Executor, Future
from dataclasses import dataclass
from pathlib import Path

from datelier.core import Dataset, DatasetRevision, JobExecutor
from datelier.inspection.comparison_settings import ComparisonSettings
from datelier.inspection.comparisons.prepare import prepare_comparison, select_bin
from datelier.inspection.comparisons.types import (
    ComparisonInput,
    ComparisonSelection,
    PreparedComparison,
)

Stamp = tuple[tuple[str, DatasetRevision | None], ...]


@dataclass
class ComparisonState:
    stamp: Stamp
    result: PreparedComparison | None = None
    message: str = "Preparing comparison…"
    future: Future[PreparedComparison] | None = None

    @property
    def busy(self) -> bool:
        return self.future is not None


class ComparisonJobs:
    def __init__(self, *, executor: Executor | None = None) -> None:
        self._executor = JobExecutor(executor, max_workers=2, name="compare")
        self._entries: dict[ComparisonSettings, ComparisonState] = {}
        self.states: tuple[ComparisonState, ...] = ()
        self._selection: Future[ComparisonSelection] | None = None
        self.selection_message = ""
        self.started = 0
        self.closed = False

    @property
    def busy(self) -> bool:
        return any(state.busy for state in self.states) or self._selection is not None

    def sync(
        self,
        settings: tuple[ComparisonSettings, ...],
        datasets: dict[str, Dataset],
        labels: dict[str, str] | None = None,
        views: dict[str, str] | None = None,
    ) -> None:
        if self.closed:
            return
        if len(settings) > 32:
            raise ValueError("Keep at most 32 comparisons")
        for recipe in settings:
            recipe.validate()
        for recipe in tuple(self._entries):
            if recipe not in settings:
                entry = self._entries.pop(recipe)
                if entry.future is not None:
                    entry.future.cancel()
        for recipe in settings:
            stamp = tuple(
                (
                    s.file_id,
                    datasets[s.file_id].revision if s.file_id in datasets else None,
                )
                for s in recipe.sources
            )
            old = self._entries.get(recipe)
            if old is not None and old.stamp == stamp:
                if old.future is not None and old.future.done():
                    future, old.future = old.future, None
                    try:
                        old.result = future.result()
                        old.message = "Comparison ready."
                    except Exception as error:
                        old.message = str(error)
                continue
            if old is not None and old.future is not None:
                old.future.cancel()
            state = ComparisonState(stamp)
            self._entries[recipe] = state
            missing = [s.file_id for s in recipe.sources if s.file_id not in datasets]
            if len(recipe.sources) < 2:
                state.message = "Map columns from at least two files."
            elif missing:
                state.message = (
                    "A mapped file is unavailable; "
                    "recover its source or change the mapping."
                )
            else:
                inputs = tuple(
                    ComparisonInput(
                        s,
                        datasets[s.file_id],
                        (labels or {}).get(
                            s.file_id, Path(datasets[s.file_id].source.path).name
                        ),
                        (views or {}).get(s.file_id, ""),
                    )
                    for s in recipe.sources
                )
                state.future = self._executor.submit(prepare_comparison, inputs, recipe)
                self.started += 1
        self.states = tuple(self._entries[s] for s in settings)

    def request_selection(
        self, result: PreparedComparison, series: int, bin_index: int, dataset: Dataset
    ) -> None:
        if self.closed:
            raise ValueError("Comparison jobs are closed")
        if not any(state.result is result for state in self.states):
            raise ValueError("The comparison changed; choose a current result")
        if result.series[series].origin.revision != dataset.revision:
            raise ValueError("The mapped file changed; refresh its comparison")
        if self._selection is not None:
            self._selection.cancel()
        self._selection = self._executor.submit(
            select_bin, result, series, bin_index, dataset
        )
        self.selection_message = "Selecting rows in the mapped source…"

    def poll_selection(
        self, datasets: dict[str, Dataset]
    ) -> ComparisonSelection | None:
        future = self._selection
        if future is None or not future.done():
            return None
        self._selection = None
        try:
            selection = future.result()
        except Exception as error:
            self.selection_message = str(error)
            return None
        dataset = datasets.get(selection.origin.file_id)
        if dataset is None or dataset.revision != selection.origin.revision:
            self.selection_message = (
                "Mapped file changed or closed; obsolete selection ignored."
            )
            return None
        self.selection_message = (
            f"{len(selection.row_ids):,} of "
            f"{selection.matches:,} matching source rows selected."
        )
        return selection

    def retry(self, recipe: ComparisonSettings) -> None:
        state = self._entries.pop(recipe, None)
        if state is not None and state.future is not None:
            state.future.cancel()

    def clear(self) -> None:
        for entry in self._entries.values():
            if entry.future is not None:
                entry.future.cancel()
        self._entries.clear()
        self.states = ()
        if self._selection is not None:
            self._selection.cancel()
            self._selection = None

    def close(self) -> None:
        self.clear()
        self.closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
