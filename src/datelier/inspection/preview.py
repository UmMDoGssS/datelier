"""Small revision-bound page cache; string conversion runs in a worker."""

from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import Executor, Future

from datelier.core import JobExecutor
from datelier.inspection.arrays.presentation import prepare_array_page
from datelier.inspection.table import (
    PAGE_COLUMNS,
    PAGE_ROWS,
    Inspection,
    PreviewPage,
    prepare_page,
)
from datelier.io.arrays.storage import ArrayStore


class PreviewCache:
    def __init__(
        self,
        *,
        executor: Executor | None = None,
        arrays: Callable[[], ArrayStore] | None = None,
    ) -> None:
        self._executor = JobExecutor(executor, max_workers=1, name="preview")
        self._inspection: Inspection | None = None
        self._pages: OrderedDict[tuple[int, int], PreviewPage] = OrderedDict()
        self._pending: dict[tuple[int, int], Future[PreviewPage]] = {}
        self.error = ""
        self._closed = False
        self._arrays = arrays

    @property
    def page_count(self) -> int:
        return len(self._pages)

    def bind(self, inspection: Inspection) -> None:
        if self._closed:
            raise RuntimeError("Preview cache is closed")
        for future in self._pending.values():
            future.cancel()
        self._pending.clear()
        self._pages.clear()
        self._inspection = inspection
        self.error = ""
        page = inspection.first_page
        self._pages[(page.row_start, page.column_start)] = page

    def poll(self) -> None:
        if self._closed:
            return
        for key, future in tuple(self._pending.items()):
            if not future.done():
                continue
            del self._pending[key]
            try:
                page = future.result()
            except Exception as error:
                self.error = f"Could not prepare preview: {error}"
                continue
            if (
                self._inspection is not None
                and page.revision == self._inspection.dataset.revision
            ):
                self._pages[key] = page
                while len(self._pages) > 4:
                    self._pages.popitem(last=False)

    def get(self, row: int, column_start: int = 0) -> PreviewPage | None:
        if self._closed:
            return None
        key = (row // PAGE_ROWS * PAGE_ROWS, column_start)
        page = self._pages.get(key)
        if page is not None:
            self._pages.move_to_end(key)
        needs_means = bool(
            self._inspection
            and any(
                name in self._inspection.array_columns
                for name in (
                    page.columns
                    if page
                    else tuple(
                        column.name
                        for column in self._inspection.schema[
                            column_start : column_start + PAGE_COLUMNS
                        ]
                    )
                )
            )
        )
        if page is not None and (page.array_ready or not needs_means):
            return page
        if (
            self._inspection is not None
            and key not in self._pending
            and len(self._pending) < 2
            and not self.error
        ):
            self._pending[key] = (
                self._executor.submit(
                    prepare_array_page,
                    self._inspection,
                    *key,
                    self._arrays() if self._arrays else None,
                )
                if needs_means
                else self._executor.submit(prepare_page, self._inspection.dataset, *key)
            )
        return page

    def retry(self) -> None:
        self.error = ""

    def close(self) -> None:
        self._closed = True
        self._inspection = None
        self._pages.clear()
        self._pending.clear()
        self._executor.shutdown(wait=False, cancel_futures=True)
