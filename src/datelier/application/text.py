"""Scoped tokenizer/profile/page coordination independently of drawing."""

from concurrent.futures import Executor

from datelier.application.media_input import MediaController, MediaInput
from datelier.inspection.text.jobs import TextJobs
from datelier.inspection.text.page_jobs import TextPageJobs


class TextController(MediaController):
    def __init__(self, executor: Executor | None = None) -> None:
        self.jobs = TextJobs(executor)
        self.pages = TextPageJobs(executor)

    def sync(self, source: MediaInput) -> None:
        self.jobs.bind(
            source.active.dataset if source.active else None,
            source.file_id,
            source.references,
            source.index,
            source.selected_rows,
        )
        self.jobs.poll()
        self.pages.sync(self.jobs.active, self.jobs.settings.viewport)

    def close(self) -> None:
        self.pages.close()
        self.jobs.close()
