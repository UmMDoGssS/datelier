"""Explicit commands; changed/closed contributors invalidate without rerunning."""

from concurrent.futures import Executor, Future
from threading import Event

from datelier.core.dataset import Dataset
from datelier.core.jobs import JobExecutor
from datelier.inspection.comparisons.types import ComparisonSelection
from datelier.inspection.images.comparisons.prepare import (
    prepare_comparison,
)
from datelier.inspection.images.comparisons.selection import select_dimension_bin
from datelier.inspection.images.comparisons.settings import ImageComparisonSettings
from datelier.inspection.images.comparisons.types import (
    ImageComparisonInput,
    PreparedImageComparison,
)
from datelier.inspection.images.profile_types import ImageProgress, ImageScopeMode


class ImageComparisonJobs:
    def __init__(self, executor: Executor | None = None) -> None:
        self._executor = JobExecutor(
            executor, max_workers=1, name="image-compare", priority=-4
        )
        self._stamp: tuple[object, ...] = ()
        self._recipe: ImageComparisonSettings | None = None
        self._inputs: tuple[ImageComparisonInput, ...] = ()
        self._future: Future[PreparedImageComparison] | None = None
        self._selection: Future[ComparisonSelection] | None = None
        self._selection_result: PreparedImageComparison | None = None
        self._stop = Event()
        self.progress = ImageProgress()
        self.active: PreparedImageComparison | None = None
        self.message = "Map two or more image fields and prepare a comparison."
        self.selection_message = ""
        self.started = 0
        self.closed = False

    @property
    def busy(self) -> bool:
        return self._future is not None

    def bind(
        self,
        recipe: ImageComparisonSettings | None,
        inputs: tuple[ImageComparisonInput, ...],
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
                    id(i.catalog),
                    id(i.arrays),
                    i.mapping,
                    i.selection
                    if i.source.profile.scope.mode == ImageScopeMode.SELECTION
                    else (),
                )
                for i in inputs
            ),
        )
        if stamp != self._stamp:
            self.clear()
            self._stamp, self._recipe, self._inputs = stamp, recipe, inputs
            self.message = "Image comparison inputs changed; prepare explicitly."

    def poll(self) -> None:
        if self._future is not None and self._future.done():
            future, self._future = self._future, None
            try:
                self.active = future.result()
                self.message = "Common-bin image comparison ready."
            except Exception as error:
                self.message = str(error)

    def request(self) -> None:
        if self.closed or self._recipe is None:
            raise ValueError("Choose an image comparison")
        self._recipe.validate()
        if (
            len(self._recipe.sources) < 2
            or tuple(i.source for i in self._inputs) != self._recipe.sources
        ):
            raise ValueError(
                "Map two available image sources; recover missing files first"
            )
        self.clear()
        self._future = self._executor.submit(
            prepare_comparison, self._inputs, self._recipe, self._stop, self.progress
        )
        self.started += 1
        self.message = "Preparing scoped images with common physical bins…"

    def request_selection(
        self,
        result: PreparedImageComparison,
        series: int,
        dimension: str,
        bin_index: int,
        dataset: Dataset,
    ) -> None:
        if self.closed or self.active is not result:
            raise ValueError("The comparison changed; prepare a current result")
        if self._selection is not None:
            self._selection.cancel()
        self._selection_result = result
        self._selection = self._executor.submit(
            select_dimension_bin, result, series, dimension, bin_index, dataset
        )
        self.selection_message = "Selecting matching rows in the mapped image source…"

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
                    "Mapped image source changed or closed; obsolete selection ignored"
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
