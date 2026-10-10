"""Prepared record collections, scoped selection and content classification."""

from concurrent.futures import Executor
from dataclasses import replace
from enum import StrEnum

from datelier.core.column_roles import ColumnRole
from datelier.inspection.arrays.mapping import ArrayLayout
from datelier.inspection.records.jobs import RecordJobs
from datelier.inspection.records.types import InspectSettings, RecordCard
from datelier.inspection.table import Inspection
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

    def poll(self, inspection: Inspection | None) -> None:
        if inspection is None:
            self.jobs.abandon()
            return
        self.jobs.sync(
            inspection.dataset, self.settings, tuple(sorted(self.selection.row_ids))
        )
        self.jobs.poll()

    def focus(self, slot: int) -> None:
        records = self.jobs.active
        if records is None or not 0 <= slot < len(records.row_ids):
            return
        self.settings = replace(self.settings, focus=slot, gallery=False)
        self.selection.choose(records.revision, (int(records.row_ids[slot]),))

    def close(self) -> None:
        self.jobs.close()
