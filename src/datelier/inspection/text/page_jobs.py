"""Visible text-page preparation follows one immutable tokenized document."""

from concurrent.futures import Executor, Future

from datelier.core.jobs import JobExecutor
from datelier.inspection.text.pages import TextPage, TextViewport, prepare_text_page
from datelier.inspection.text.types import TokenizedDocument


class TextPageJobs:
    def __init__(self, executor: Executor | None = None) -> None:
        self._executor = JobExecutor(
            executor, max_workers=1, name="text-page", priority=-10
        )
        self._document: TokenizedDocument | None = None
        self._viewport: TextViewport | None = None
        self._future: Future[TextPage] | None = None
        self.active: TextPage | None = None
        self.message = ""
        self.closed = False

    def sync(self, document: TokenizedDocument | None, viewport: TextViewport) -> None:
        if self.closed:
            return
        if document is not self._document or viewport != self._viewport:
            self.abandon()
            self._document, self._viewport = document, viewport
            if document is not None:
                self._future = self._executor.submit(
                    prepare_text_page, document, viewport
                )
                self.message = "Preparing text page…"
        if self._future is not None and self._future.done():
            future, self._future = self._future, None
            try:
                self.active = future.result()
                self.message = ""
            except Exception as error:
                self.message = f"Text page failed: {error}"

    def abandon(self) -> None:
        if self._future is not None:
            self._future.cancel()
        self._future = None
        self._document = None
        self._viewport = None
        self.active = None

    def close(self) -> None:
        self.closed = True
        self.abandon()
        self._executor.shutdown(wait=False, cancel_futures=True)
