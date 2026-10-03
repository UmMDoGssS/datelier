"""Dataset identity and revision contracts, independent of rendering/imports."""

from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import polars as pl


@dataclass(frozen=True)
class SourceReference:
    path: Path
    size_bytes: int
    modified_ns: int


@dataclass(frozen=True)
class DatasetRevision:
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
        )
