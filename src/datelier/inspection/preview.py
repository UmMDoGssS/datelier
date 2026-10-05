"""Small revision-bound page cache; string conversion runs in a worker."""

from collections import OrderedDict
from concurrent.futures import Executor, Future

from datelier.core.jobs import JobExecutor
from datelier.inspection.table import PAGE_ROWS, Inspection, PreviewPage, prepare_page


class PreviewCache:
    def __init__(self, *, executor: Executor | None = None) -> None:
        self._executor = JobExecutor(executor, max_workers=1, name="preview")
        self._inspection: Inspection | None = None
        self._pages: OrderedDict[tuple[int, int], PreviewPage] = OrderedDict()
        self._pending: dict[tuple[int, int], Future[PreviewPage]] = {}
        self.error = ""

    @property
    def page_count(self) -> int:
        return len(self._pages)

    def bind(self, inspection: Inspection) -> None:
        for future in self._pending.values():
            future.cancel()
        self._pending.clear()
        self._pages.clear()
        self._inspection = inspection
        self.error = ""
        page = inspection.first_page
        self._pages[(page.row_start, page.column_start)] = page

    def poll(self) -> None:
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
        key = (row // PAGE_ROWS * PAGE_ROWS, column_start)
        page = self._pages.get(key)
        if page is not None:
            self._pages.move_to_end(key)
            return page
        if (
            self._inspection is not None
            and key not in self._pending
            and len(self._pending) < 2
            and not self.error
        ):
            self._pending[key] = self._executor.submit(
                prepare_page, self._inspection.dataset, *key
            )
        return None

    def retry(self) -> None:
        self.error = ""

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
