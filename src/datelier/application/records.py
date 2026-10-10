"""Prepared record collections, scoped selection and content classification."""

from concurrent.futures import Executor
from dataclasses import replace
from enum import StrEnum

import polars as pl

from datelier.application.columns import ColumnChoice
from datelier.application.sources.columns import record_mapping
from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset, DatasetRevision
from datelier.inspection.arrays.mapping import ArrayLayout
from datelier.inspection.records.jobs import RecordJobs
from datelier.inspection.records.types import (
    InspectSettings,
    RecordCard,
    RecordField,
    RecordMode,
)
from datelier.inspection.table import Inspection
from datelier.inspection.text.list_records import is_text_list
from datelier.io.types import ArrayOptions
from datelier.plotting.selection import LinkedSelection


class RecordKind(StrEnum):
    VALUE = "Value"
    NESTED = "Nested"
    TEXT = "Text"
    IMAGE = "Image"
    AUDIO = "Audio"
    ARRAY = "Array"


def record_kind(inspection: Inspection, card: RecordCard) -> RecordKind:
    primary = card.primary
    if primary is None:
        return RecordKind.VALUE
    if primary.lines is not None:
        return RecordKind.NESTED
    mapping = record_mapping(inspection, primary.name)
    if mapping is not None:
        return {
            ArrayLayout.AUDIO: RecordKind.AUDIO,
            ArrayLayout.IMAGE: RecordKind.IMAGE,
            ArrayLayout.HEATMAP: RecordKind.IMAGE,
        }.get(mapping.layout, RecordKind.ARRAY)
    role = inspection.dataset.role(primary.name).role
    if inspection.dataset.table.schema[primary.name] == pl.String and role not in (
        ColumnRole.IMAGE,
        ColumnRole.AUDIO,
    ):
        return RecordKind.TEXT
    return {
        ColumnRole.TEXT: RecordKind.TEXT,
        ColumnRole.EXTERNAL_TEXT: RecordKind.TEXT,
        ColumnRole.IMAGE: RecordKind.IMAGE,
        ColumnRole.AUDIO: RecordKind.AUDIO,
    }.get(role, RecordKind.VALUE)


class RecordController:
    def __init__(self, selection: LinkedSelection, executor: Executor) -> None:
        self.jobs = RecordJobs(executor)
        self.settings = InspectSettings()
        self.selection = selection
        self.choices: tuple[ColumnChoice, ...] = ()
        self._inspection: Inspection | None = None
        self.text_list = False
        self.has_mapped_payload = False

    def bind(self, dataset: Dataset) -> None:
        columns = dataset.table.columns
        self.settings = replace(
            self.settings,
            primary=self.settings.primary
            if self.settings.primary in columns
            else next(iter(columns), None),
            supporting=tuple(columns)
            if self.settings.supporting is None
            else tuple(name for name in self.settings.supporting if name in columns),
        )

    def poll(self, inspection: Inspection | None) -> None:
        self._inspection = inspection
        self.choices = (
            tuple(
                ColumnChoice(info.name, info.role.value)
                for info in inspection.dataset.roles or ()
            )
            if inspection
            else ()
        )
        if inspection is None:
            self.jobs.abandon()
            return
        self.bind(inspection.dataset)
        self.has_mapped_payload = (
            isinstance(inspection.imported.options, ArrayOptions)
            and inspection.imported.options.mapping is not None
        )
        dtype = inspection.dataset.table.schema.get(self.settings.primary or "")
        self.text_list = dtype is not None and is_text_list(dtype)
        self.jobs.sync(
            inspection.dataset, self.settings, tuple(sorted(self.selection.row_ids))
        )
        self.jobs.poll()

    def presentation(self, card: RecordCard) -> RecordCard:
        inspection = self._inspection
        options = inspection.imported.options if inspection else None
        if (
            self.settings.mapped_payload is not False
            and isinstance(options, ArrayOptions)
            and options.mapping
        ):
            return replace(
                card,
                primary=RecordField(
                    options.mapping.member,
                    "Mapped payload; source record identity is preserved.",
                ),
            )
        return card

    def kind(self, card: RecordCard) -> RecordKind:
        if (
            self.settings.text_elements
            and self._inspection
            and card.primary
            and (dtype := self._inspection.dataset.table.schema.get(card.primary.name))
            is not None
            and is_text_list(dtype)
        ):
            return RecordKind.TEXT
        return (
            record_kind(self._inspection, card)
            if self._inspection
            else RecordKind.VALUE
        )

    def current_kind(self) -> RecordKind:
        inspection, name = self._inspection, self.settings.primary
        if (
            self.has_mapped_payload
            and self.settings.mapped_payload is not False
            and inspection
        ):
            card = self.presentation(RecordCard(0, 0, None, ()))
            return record_kind(inspection, card)
        if self.text_list and self.settings.text_elements:
            return RecordKind.TEXT
        if (
            inspection is None
            or name is None
            or name not in inspection.dataset.table.columns
        ):
            return RecordKind.VALUE
        if inspection.dataset.table.schema[name].is_nested():
            return RecordKind.NESTED
        return record_kind(inspection, RecordCard(0, 0, RecordField(name, ""), ()))

    def select(self, card: RecordCard, toggle: bool) -> None:
        if self._inspection:
            self.selection.choose(
                self._inspection.dataset.revision, (card.row_id,), toggle=toggle
            )

    def focus(self, slot: int) -> None:
        records = self.jobs.active
        if records is None or not 0 <= slot < len(records.row_ids):
            return
        self.settings = replace(self.settings, focus=slot, gallery=False)
        self.selection.choose(records.revision, (int(records.row_ids[slot]),))

    def open_position(
        self,
        revision: DatasetRevision,
        position: int,
        row_id: int,
        primary: str | None,
        mapped: bool = False,
    ) -> bool:
        inspection = self._inspection
        if (
            inspection is None
            or inspection.dataset.revision != revision
            or not 0 <= position < inspection.row_count
            or int(inspection.dataset.row_ids[position]) != row_id
        ):
            return False
        self.settings = replace(
            self.settings,
            mode=RecordMode.RANGE,
            start=position + 1,
            count=1,
            focus=0,
            gallery=False,
            primary=primary,
            mapped_payload=mapped,
        )
        self.selection.choose(revision, (row_id,))
        return True

    @property
    def revision(self) -> DatasetRevision | None:
        return self._inspection.dataset.revision if self._inspection else None

    def close(self) -> None:
        self._inspection = None
        self.jobs.close()
