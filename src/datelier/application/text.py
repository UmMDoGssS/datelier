"""Scoped tokenizer/profile/page coordination independently of drawing."""

from concurrent.futures import Executor
from dataclasses import replace

from datelier.application.media_input import MediaController, MediaInput
from datelier.application.text_profiles import length_rows, statistic_rows
from datelier.inspection.text.jobs import TextJobs
from datelier.inspection.text.list_records import is_text_list
from datelier.inspection.text.page_jobs import TextPageJobs


class TextController(MediaController):
    def __init__(self, executor: Executor | None = None) -> None:
        self._source: MediaInput | None = None
        self.jobs = TextJobs(executor)
        self.pages = TextPageJobs(executor)
        self.corpus = TextJobs(executor)
        self.profile_column: str | None = None
        self.profile_tab = "Statistics"
        self.record_list = False
        self.statistics: tuple[tuple[str, int | float | None], ...] = ()
        self.lengths: tuple[tuple[object, ...], ...] = ()
        self._profile = None
        self.original_height = 160.0
        self.token_height = 200.0

    def sync(self, source: MediaInput) -> None:
        self._source = source
        dtype = (
            source.active.dataset.table.schema.get(self.jobs.settings.column or "")
            if source.active
            else None
        )
        self.record_list = dtype is not None and is_text_list(dtype)
        self.jobs.bind(
            source.active.dataset if source.active else None,
            source.file_id,
            source.references,
            source.index,
            source.selected_rows,
        )
        self.jobs.poll()
        self.pages.sync(self.jobs.active, self.jobs.settings.viewport)
        if self.profile_column is None:
            self.profile_column = self.jobs.settings.column
        self.corpus.settings = replace(
            self.jobs.settings, column=self.profile_column, position=0
        )
        self.corpus.bind(
            source.active.dataset if source.active else None,
            source.file_id,
            source.references,
            source.index,
            source.selected_rows,
        )
        tokens = self.corpus.settings.tokens
        self.corpus.poll()
        if self.corpus.settings.tokens != tokens:
            self.jobs.settings = replace(
                self.jobs.settings, tokens=self.corpus.settings.tokens
            )
        if self._profile is not self.corpus.profile:
            self._profile = self.corpus.profile
            profile = self._profile.profile if self._profile else None
            self.statistics = statistic_rows(profile)
            self.lengths = length_rows(profile)

    def request_record(self, column: str, position: int) -> None:
        if self._source:
            self.jobs.settings = replace(
                self.jobs.settings, column=column, position=position
            )
            self.sync(self._source)
            self.jobs.request_document()

    def request_profile(self, column: str) -> None:
        self.profile_column = column
        if self._source:
            self.sync(self._source)
            self.corpus.request_profile()

    def request_training(self, column: str) -> None:
        self.profile_column = column
        if self._source:
            self.sync(self._source)
            self.corpus.request_training()

    def close(self) -> None:
        self._source = None
        self.pages.close()
        self.jobs.close()
        self.corpus.close()
        self._profile = None
        self.statistics = self.lengths = ()
