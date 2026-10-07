"""File/view-owned text workers; commands publish only into their current scope."""

from concurrent.futures import Executor, Future
from dataclasses import replace
from pathlib import Path

from datelier.core.dataset import Dataset, DatasetRevision
from datelier.core.jobs import JobExecutor
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.text.records import read_document
from datelier.inspection.text.tokenization import TextTokenizer, import_tokenizer
from datelier.inspection.text.types import (
    TextSettings,
    TokenizedDocument,
    TokenizerReference,
)


def prepare_document(
    dataset: Dataset,
    file_id: str,
    settings: TextSettings,
    references: ReferenceSettings,
    index: ReferenceIndex | None,
) -> TokenizedDocument:
    settings.validate()
    if settings.column is None:
        raise ValueError("Choose a text field")
    document = read_document(
        dataset,
        file_id,
        settings.column,
        settings.position,
        source=settings.source,
        encoding=settings.encoding,
        references=references,
        index=index,
    )
    return TextTokenizer(settings.tokens).encode(document)


class TextJobs:
    def __init__(self, executor: Executor | None = None) -> None:
        self._executor = JobExecutor(executor, max_workers=1, name="text", priority=-5)
        self.settings = TextSettings()
        self._stamp: (
            tuple[str, DatasetRevision, TextSettings, ReferenceSettings] | None
        ) = None
        self._dataset: Dataset | None = None
        self._index: ReferenceIndex | None = None
        self._document: Future[TokenizedDocument] | None = None
        self._import: Future[TokenizerReference] | None = None
        self.active: TokenizedDocument | None = None
        self.message = "Choose a text field and prepare a record."
        self.closed = False

    @property
    def busy(self) -> bool:
        return self._document is not None or self._import is not None

    def bind(
        self,
        dataset: Dataset | None,
        file_id: str,
        references: ReferenceSettings,
        index: ReferenceIndex | None,
    ) -> None:
        stamp = (
            (file_id, dataset.revision, self.settings, references) if dataset else None
        )
        if stamp != self._stamp or index is not self._index:
            self.abandon()
            self._dataset = dataset
            self._stamp = stamp
            self._index = index

    def request_document(self) -> None:
        if self.closed or self._dataset is None or self._stamp is None:
            raise ValueError("Open a text source before preparing records")
        self.abandon()
        self._document = self._executor.submit(
            prepare_document,
            self._dataset,
            self._stamp[0],
            self.settings,
            self._stamp[3],
            self._index,
        )
        self.message = "Preparing complete text and tokens…"

    def request_import(self, path: Path) -> None:
        if self.closed:
            raise ValueError("This text view is closed")
        self.abandon()
        self._import = self._executor.submit(import_tokenizer, path)
        self.message = "Validating local tokenizer configuration…"

    def poll(self) -> None:
        if self.closed:
            return
        if self._import and self._import.done():
            future, self._import = self._import, None
            try:
                reference = future.result()
                self.settings = replace(
                    self.settings,
                    tokens=replace(
                        self.settings.tokens, mode=reference.mode, artifact=reference
                    ),
                )
                self.message = f"Loaded local {reference.mode}: {reference.path}"
            except Exception as error:
                self.message = (
                    f"Cannot load tokenizer: {error}. Choose a JSON file and retry."
                )
        if self._document and self._document.done():
            future, self._document = self._document, None
            try:
                self.active = future.result()
                self.message = (
                    f"{self.active.document.status}: "
                    f"{self.active.count:,} counted tokens; "
                    f"{len(self.active.document.text):,} original code points."
                )
            except Exception as error:
                self.message = (
                    f"Cannot prepare text: {error}. Reload the tokenizer or retry."
                )

    def abandon(self) -> None:
        for future in (self._document, self._import):
            if future is not None:
                future.cancel()
        self._document = None
        self._import = None
        self.active = None

    def close(self) -> None:
        self.closed = True
        self.abandon()
        self._stamp = None
        self._dataset = None
        self._index = None
        self._executor.shutdown(wait=False, cancel_futures=True)
