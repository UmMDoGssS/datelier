"""Scoped tokenizer/profile/page coordination independently of drawing."""

from concurrent.futures import Executor
from dataclasses import replace

from datelier.application.media_input import MediaController, MediaInput
from datelier.inspection.text.jobs import TextJobs
from datelier.inspection.text.page_jobs import TextPageJobs


class TextController(MediaController):
    def __init__(self, executor: Executor | None = None) -> None:
        self._source: MediaInput | None = None
        self.jobs = TextJobs(executor)
        self.pages = TextPageJobs(executor)
        self.original_height = 160.0
        self.token_height = 200.0

    def sync(self, source: MediaInput) -> None:
        self._source = source
        self.jobs.bind(
            source.active.dataset if source.active else None,
            source.file_id,
            source.references,
            source.index,
            source.selected_rows,
        )
        self.jobs.poll()
        self.pages.sync(self.jobs.active, self.jobs.settings.viewport)

    def request_record(self, column: str, position: int) -> None:
        if self._source:
            self.jobs.settings = replace(
                self.jobs.settings, column=column, position=position
            )
            self.sync(self._source)
            self.jobs.request_document()

    def close(self) -> None:
        self._source = None
        self.pages.close()
        self.jobs.close()
