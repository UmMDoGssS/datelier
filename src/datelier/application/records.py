"""Prepared record collections, scoped selection and content classification."""

from concurrent.futures import Executor
from dataclasses import replace
from enum import StrEnum

import polars as pl

from datelier.application.columns import ColumnChoice
from datelier.core.column_roles import ColumnRole
from datelier.core.dataset import Dataset
from datelier.inspection.arrays.mapping import ArrayLayout
from datelier.inspection.records.jobs import RecordJobs
from datelier.inspection.records.types import InspectSettings, RecordCard, RecordField
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
    options = inspection.imported.options
    mapping = (
        options.mapping_for(inspection.imported.array_catalog, primary.name)
        if isinstance(options, ArrayOptions)
        else None
    )
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
        dtype = inspection.dataset.table.schema.get(self.settings.primary or "")
        self.text_list = dtype is not None and is_text_list(dtype)
        self.jobs.sync(
            inspection.dataset, self.settings, tuple(sorted(self.selection.row_ids))
        )
        self.jobs.poll()

    def kind(self, card: RecordCard) -> RecordKind:
        if (
            self.settings.text_elements
            and self._inspection
            and card.primary
            and is_text_list(self._inspection.dataset.table.schema[card.primary.name])
        ):
            return RecordKind.TEXT
        return (
            record_kind(self._inspection, card)
            if self._inspection
            else RecordKind.VALUE
        )

    def current_kind(self) -> RecordKind:
        if self.text_list and self.settings.text_elements:
            return RecordKind.TEXT
        inspection, name = self._inspection, self.settings.primary
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

    def close(self) -> None:
        self._inspection = None
        self.jobs.close()
