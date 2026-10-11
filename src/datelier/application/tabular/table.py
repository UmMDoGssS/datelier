"""Prepared table metadata and source-row navigation, independently of widgets."""

from dataclasses import dataclass

from datelier.application.sources.columns import record_mapping
from datelier.application.tabular.columns import ColumnChoice
from datelier.application.tabular.presentation import PresentationController
from datelier.core.column_roles import REFERENCE_ROLES, ColumnRole
from datelier.core.dataset import DatasetRevision
from datelier.inspection.presentation import NumericBounds
from datelier.inspection.preview import PreviewCache
from datelier.inspection.table import Inspection
from datelier.plotting.scatter import LinkedSelection


@dataclass(frozen=True)
class TableColumn:
    name: str
    dtype: str
    role: ColumnRole
    reason: str
    reference: bool
    bounds: NumericBounds | None
    null_count: int
    distinct: int | None


@dataclass(frozen=True)
class TableSnapshot:
    revision: DatasetRevision
    rows: int
    columns: tuple[TableColumn, ...]


class TableController:
    def __init__(self, pages: PreviewCache, selection: LinkedSelection) -> None:
        self.pages = pages
        self.selection = selection
        self.presentation = PresentationController()
        self.snapshot: TableSnapshot | None = None
        self.reference_columns: tuple[ColumnChoice, ...] = ()
        self.column_start = 0
        self.target_row = 1
        self.jump = False

    def refresh(self, inspection: Inspection | None) -> None:
        revision = inspection.dataset.revision if inspection else None
        if revision == (self.snapshot.revision if self.snapshot else None):
            return
        bounds = {b.column: b for b in inspection.bounds} if inspection else {}
        self.snapshot = (
            TableSnapshot(
                inspection.dataset.revision,
                inspection.row_count,
                tuple(
                    TableColumn(
                        c.name,
                        c.dtype,
                        (role := inspection.dataset.role(c.name)).role,
                        role.reason,
                        role.role in REFERENCE_ROLES
                        and record_mapping(inspection, c.name) is None,
                        bounds.get(c.name),
                        c.null_count,
                        role.distinct,
                    )
                    for c in inspection.schema
                ),
            )
            if inspection
            else None
        )
        self.column_start = 0
        self.target_row = 1
        self.jump = True
        self.reference_columns = (
            tuple(
                ColumnChoice(c.name, c.role.value)
                for c in self.snapshot.columns
                if c.reference
            )
            if self.snapshot
            else ()
        )

    def go_to(self, position: int) -> None:
        self.target_row = position + 1
        self.jump = True
