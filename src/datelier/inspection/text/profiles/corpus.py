"""Explicit text corpus scope and streaming source records for worker commands."""

from collections.abc import Iterator
from threading import Event, Lock
from typing import cast

import polars as pl

from datelier.core import ColumnRole, Dataset
from datelier.inspection.records import InspectSettings, RecordMode
from datelier.inspection.records.prepare import prepare_records
from datelier.inspection.references import ReferenceSettings
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.text.profiles.lists import (
    element_documents,
    is_text_field,
    is_text_list,
)
from datelier.inspection.text.records import read_value
from datelier.inspection.text.types import (
    CorpusMode,
    TextDocument,
    TextOrigin,
    TextScope,
    TextSettings,
    TextSource,
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
    table = dataset.table
    if settings.column not in table.columns or not is_text_field(
        table.schema[settings.column]
    ):
        raise ValueError("Choose a String or List[String] field for text inspection")
    if is_text_list(table.schema[settings.column]):
        if settings.source == TextSource.EXTERNAL:
            raise ValueError("Text lists use inline string elements")
        elements = 0
        values, row_ids = table.get_column(settings.column), dataset.row_ids
        for done, position in enumerate(positions, 1):
            check_abandoned(stop)
            origin = TextOrigin(
                file_id, dataset.revision, int(row_ids[int(position)]), settings.column
            )
            for document in element_documents(values[int(position)], origin, stop):
                yield document
                elements += 1
                if elements % 256 == 0:
                    stop.wait(0.001)
            progress.update("Preparing corpus rows", done, len(positions))
        check_abandoned(stop)
        return
    values, row_ids = table.get_column(settings.column), dataset.row_ids
    external = settings.source == TextSource.EXTERNAL or (
        settings.source == TextSource.AUTO
        and dataset.role(settings.column).role
        in (ColumnRole.EXTERNAL_TEXT, ColumnRole.PATH)
    )
    for start in range(0, len(positions), 256):
        check_abandoned(stop)
        chosen = positions.slice(start, 256)
        # Polars String dtype was checked above. Small library-input chunks
        # avoid per-record frame/schema clones and never copy the whole corpus.
        chunk = cast(list[str | None], values.gather(chosen).to_list())
        for offset, (row_id, value) in enumerate(
            zip(row_ids.gather(chosen), chunk, strict=True)
        ):
            check_abandoned(stop)
            origin = TextOrigin(file_id, dataset.revision, int(row_id), settings.column)
            yield read_value(
                origin,
                value,
                dataset.source.path,
                external=external,
                encoding=settings.encoding,
                references=references,
                index=index,
            )
            progress.update(
                "Preparing corpus records", start + offset + 1, len(positions)
            )
        # CPU-bound Python/token alignment must yield the GIL between chunks
        # so the native renderer remains responsive during complete analysis.
        stop.wait(0.001)
    check_abandoned(stop)
    progress.update("Corpus records prepared", len(positions), len(positions))
