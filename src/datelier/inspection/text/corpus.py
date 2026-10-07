"""Explicit text corpus scope and streaming source records for worker commands."""

from collections.abc import Iterator
from threading import Event, Lock

import polars as pl

from datelier.core.dataset import Dataset
from datelier.inspection.records.prepare import prepare_records
from datelier.inspection.records.types import InspectSettings, RecordMode
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.text.records import read_document
from datelier.inspection.text.types import (
    CorpusMode,
    TextDocument,
    TextScope,
    TextSettings,
)


class TextProgress:
    def __init__(self) -> None:
        self._lock = Lock()
        self._value = ("", 0, 0)

    @property
    def value(self) -> tuple[str, int, int]:
        with self._lock:
            return self._value

    def update(self, phase: str, done: int, total: int) -> None:
        with self._lock:
            self._value = (phase, done, total)


def check_abandoned(stop: Event) -> None:
    if stop.is_set():
        raise ValueError("Text job abandoned")


def corpus_positions(
    dataset: Dataset, scope: TextScope, selection: tuple[int, ...]
) -> pl.Series:
    scope.validate()
    if scope.mode == CorpusMode.COLLECTION:
        return pl.int_range(0, dataset.table.height, eager=True)
    settings = InspectSettings(
        RecordMode(scope.mode.value), scope.start, scope.count, scope.seed
    )
    return prepare_records(dataset, settings, selection).positions


def corpus_documents(
    dataset: Dataset,
    file_id: str,
    settings: TextSettings,
    positions: pl.Series,
    references: ReferenceSettings,
    index: ReferenceIndex | None,
    stop: Event,
    progress: TextProgress,
) -> Iterator[TextDocument]:
    if settings.column is None:
        raise ValueError("Choose a text field")
    for number, position in enumerate(positions):
        check_abandoned(stop)
        yield read_document(
            dataset,
            file_id,
            settings.column,
            int(position),
            source=settings.source,
            encoding=settings.encoding,
            references=references,
            index=index,
        )
        progress.update("Reading records", number + 1, len(positions))
    check_abandoned(stop)
    progress.update(
        "Training / finalizing (trainer has no progress API)",
        len(positions),
        len(positions),
    )
