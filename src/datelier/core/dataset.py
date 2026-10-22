"""Dataset identity and revision contracts, independent of rendering/imports."""

from dataclasses import dataclass, field, replace
from pathlib import Path
from uuid import UUID, uuid4

import polars as pl

from datelier.core.column_roles import ColumnRole, RoleInfo, allowed_roles, infer_roles


@dataclass(frozen=True)
class SourceReference:
    path: Path
    size_bytes: int
    modified_ns: int


@dataclass(frozen=True)
class DatasetRevision:
    """Identity of one dataset state, not a row number or a display position.

    The dataset UUID survives edits; each published state has a fresh token so
    late jobs cannot replace newer prepared results.
    """

    dataset_id: UUID
    token: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class Dataset:
    """Polars data with source-row IDs kept outside the user's column namespace.

    Public access returns shallow clones (shared immutable column buffers), so
    callers cannot mutate this revision through Polars' in-place frame methods.
    IDs are assigned at import and must travel with rows through later edits.
    """

    source: SourceReference
    revision: DatasetRevision
    source_row_count: int
    _table: pl.DataFrame = field(repr=False)
    _row_ids: pl.Series = field(repr=False)
    roles: tuple[RoleInfo, ...] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.roles is None:
            object.__setattr__(self, "roles", infer_roles(self._table))

    def role(self, name: str) -> RoleInfo:
        return next(info for info in self.roles or () if info.name == name)

    def columns_for(self, role: ColumnRole) -> tuple[str, ...]:
        return tuple(info.name for info in self.roles or () if info.role == role)

    def with_role(self, name: str, role: ColumnRole | None) -> Dataset:
        dtype = self._table.get_column(name).dtype
        if role is not None and role not in allowed_roles(dtype):
            raise ValueError(f"{role} is incompatible with {dtype}")
        roles = tuple(
            replace(info, override=role) if info.name == name else info
            for info in self.roles or ()
        )
        return replace(
            self, revision=DatasetRevision(self.revision.dataset_id), roles=roles
        )

    @classmethod
    def from_source(cls, table: pl.DataFrame, source: SourceReference) -> Dataset:
        return cls(
            source,
            DatasetRevision(uuid4()),
            table.height,
            table.clone(),
            pl.Series("source_row_id", range(table.height), dtype=pl.UInt64),
        )

    @property
    def table(self) -> pl.DataFrame:
        return self._table.clone()

    @property
    def row_ids(self) -> pl.Series:
        return self._row_ids.clone()

    def with_rows(self, table: pl.DataFrame, row_ids: pl.Series) -> Dataset:
        """Publish an aligned revision; never infer identity from display order."""
        if row_ids.dtype != pl.UInt64 or len(row_ids) != table.height:
            raise ValueError("Each row requires one UInt64 source-row ID")
        if row_ids.null_count() or row_ids.n_unique() != len(row_ids):
            raise ValueError("Source-row IDs must be non-null and unique")
        if (row_ids >= self.source_row_count).any():
            raise ValueError("Source-row ID is outside the imported dataset")
        return Dataset(
            self.source,
            DatasetRevision(self.revision.dataset_id),
            self.source_row_count,
            table.clone(),
            row_ids.clone(),
            infer_roles(table, self.roles or ()),
        )
