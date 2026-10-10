"""Prepared table metadata and source-row navigation, independently of widgets."""

from dataclasses import dataclass

from datelier.core.dataset import DatasetRevision
from datelier.inspection.preview import PreviewCache
from datelier.inspection.table import ColumnSummary, Inspection
from datelier.plotting.selection import LinkedSelection


@dataclass(frozen=True)
class TableSnapshot:
    revision: DatasetRevision
    rows: int
    columns: tuple[ColumnSummary, ...]


class TableController:
    def __init__(self, pages: PreviewCache, selection: LinkedSelection) -> None:
        self.pages = pages
        self.selection = selection
        self.snapshot: TableSnapshot | None = None
        self.column_start = 0
        self.target_row = 1
        self.jump = False

    def refresh(self, inspection: Inspection | None) -> None:
        revision = inspection.dataset.revision if inspection else None
        if revision == (self.snapshot.revision if self.snapshot else None):
            return
        self.snapshot = (
            TableSnapshot(
                inspection.dataset.revision, inspection.row_count, inspection.schema
            )
            if inspection
            else None
        )
        self.column_start = 0
        self.target_row = 1
        self.jump = True

    def go_to(self, position: int) -> None:
        self.target_row = position + 1
        self.jump = True
