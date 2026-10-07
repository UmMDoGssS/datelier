"""File/view-owned text workers; commands publish only into their current scope."""

from concurrent.futures import Executor, Future
from dataclasses import replace
from pathlib import Path
from threading import Event

from datelier.core.dataset import Dataset, DatasetRevision
from datelier.core.jobs import JobExecutor
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.text.corpus import TextProgress
from datelier.inspection.text.records import read_document
from datelier.inspection.text.tokenization import TextTokenizer, import_tokenizer
from datelier.inspection.text.training import (
    TrainedTokenizer,
    remove_unaccepted,
    train_tokenizer,
)
from datelier.inspection.text.types import (
    CorpusMode,
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
        # Cleanup borrows the same shared workers, but its queued file removals
        # must survive closure of the preparation scope.
        self._cleanup = JobExecutor(
            executor, max_workers=1, name="text-cleanup", priority=-10
        )
        self.settings = TextSettings()
        self._stamp: (
            tuple[
                str, DatasetRevision, TextSettings, ReferenceSettings, tuple[int, ...]
            ]
            | None
        ) = None
        self._dataset: Dataset | None = None
        self._index: ReferenceIndex | None = None
        self._document: Future[TokenizedDocument] | None = None
        self._import: Future[TokenizerReference] | None = None
        self._training: Future[TrainedTokenizer] | None = None
        self._stop = Event()
        self.progress = TextProgress()
        self.training_summary = ""
        self.active: TokenizedDocument | None = None
        self.message = "Choose a text field and prepare a record."
        self.closed = False

    @property
    def busy(self) -> bool:
        return any(
            f is not None for f in (self._document, self._import, self._training)
        )

    def bind(
        self,
        dataset: Dataset | None,
        file_id: str,
        references: ReferenceSettings,
        index: ReferenceIndex | None,
        selection: tuple[int, ...] = (),
    ) -> None:
        chosen = selection if self.settings.scope.mode == CorpusMode.SELECTION else ()
        stamp = (
            (file_id, dataset.revision, self.settings, references, chosen)
            if dataset
            else None
        )
        if stamp != self._stamp or index is not self._index:
            pending, prepared = self.busy, self.active is not None
            self.abandon()
            if pending:
                self.message = (
                    "Text inputs changed; executing work is abandoned "
                    "and cannot publish."
                )
            elif prepared:
                self.message = "Text inputs changed; prepare the record again."
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
        if self._training and self._training.done():
            future, self._training = self._training, None
            try:
                result = future.result()
                self.settings = replace(
                    self.settings,
                    tokens=replace(
                        self.settings.tokens,
                        mode=result.reference.mode,
                        artifact=result.reference,
                    ),
                )
                self.training_summary = (
                    f"Trained {result.reference.mode} on "
                    f"{result.documents:,} documents "
                    f"from {result.requested:,} chosen records; "
                    f"{result.nulls:,} null and {result.empty:,} empty excluded. "
                    f"{result.tokenless:,} documents without pieces excluded. "
                    f"Input SHA-256: {result.input_sha256}"
                )
                self.message = self.training_summary
            except Exception as error:
                self.message = (
                    f"Training failed: {error}. Prior tokenizer settings retained."
                )
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
        self._stop.set()
        if (
            self._training is not None
            and self._training.done()
            and not self._training.cancelled()
        ):
            try:
                self._cleanup.submit(remove_unaccepted, self._training.result())
            except Exception:
                pass  # Failed training has no completed artifact to remove.
        if self._training is not None:
            self._training.cancel()
        self._training = None
        for future in (self._document, self._import):
            if future is not None:
                future.cancel()
        self._document = None
        self._import = None
        self.active = None

    def request_training(self, selection: tuple[int, ...] | None = None) -> None:
        if self.closed or self._dataset is None or self._stamp is None:
            raise ValueError("Open a text source before training")
        self.abandon()
        self._stop = stop = Event()
        self.progress = TextProgress()
        future = self._training = self._executor.submit(
            train_tokenizer,
            self._dataset,
            self._stamp[0],
            self.settings,
            self._stamp[4] if selection is None else selection,
            self._stamp[3],
            self._index,
            stop,
            self.progress,
        )

        def retire(completed: Future[TrainedTokenizer]) -> None:
            # This callback executes in the worker. A discarded future cannot
            # leave an unaccepted artifact after source/view closure.
            if stop.is_set() and not completed.cancelled():
                try:
                    remove_unaccepted(completed.result())
                except Exception:
                    pass  # Failed training has already removed its partial files.

        future.add_done_callback(retire)
        self.message = "Training tokenizer on the chosen corpus scope…"

    def close(self) -> None:
        self.closed = True
        self.abandon()
        self._stamp = None
        self._dataset = None
        self._index = None
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._cleanup.shutdown(wait=False, cancel_futures=False)
