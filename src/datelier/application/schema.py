"""Prepared column metadata and revision-bound interpretation commands."""

from collections.abc import Callable
from dataclasses import dataclass

from datelier.core.column_roles import ColumnRole, RoleInfo, allowed_roles
from datelier.core.dataset import DatasetRevision
from datelier.inspection.table import Inspection
from datelier.pipeline.operations import SetColumnRole


@dataclass(frozen=True)
class SchemaColumn:
    name: str
    dtype: str
    role: RoleInfo
    options: tuple[ColumnRole | None, ...]


@dataclass(frozen=True)
class SchemaSnapshot:
    revision: DatasetRevision
    rows: int
    columns: tuple[SchemaColumn, ...]


class SchemaController:
    def __init__(self, request: Callable[[SetColumnRole], None]) -> None:
        self._request = request
        self.snapshot: SchemaSnapshot | None = None
        self.busy = False
        self.error = ""

    def refresh(self, inspection: Inspection | None, *, busy: bool) -> None:
        self.busy = busy
        revision = inspection.dataset.revision if inspection is not None else None
        if revision == (self.snapshot.revision if self.snapshot else None):
            return
        self.error = ""
        if inspection is None:
            self.snapshot = None
            return
        dataset = inspection.dataset
        schema = dataset.table.schema
        roles = {info.name: info for info in dataset.roles or ()}
        self.snapshot = SchemaSnapshot(
            dataset.revision,
            inspection.row_count,
            tuple(
                SchemaColumn(
                    column.name,
                    column.dtype,
                    roles[column.name],
                    (None, *allowed_roles(schema[column.name])),
                )
                for column in inspection.schema
            ),
        )

    def set_role(
        self, revision: DatasetRevision, name: str, role: ColumnRole | None
    ) -> None:
        snapshot = self.snapshot
        if snapshot is None or snapshot.revision != revision:
            self.error = "The column view changed; choose its interpretation again."
            return
        if self.busy:
            self.error = "Wait for the current edit before changing interpretations."
            return
        column = next((c for c in snapshot.columns if c.name == name), None)
        if column is None or role not in column.options:
            self.error = "That interpretation is unavailable for this column."
            return
        try:
            self._request(SetColumnRole(name, role))
            self.error = ""
            self.busy = True
        except ValueError as error:
            self.error = str(error)
