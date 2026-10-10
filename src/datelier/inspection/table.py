"""Prepared summaries and bounded preview pages; no GUI dependencies."""

from dataclasses import dataclass

import polars as pl

from datelier.core.column_roles import REFERENCE_ROLES
from datelier.core.dataset import Dataset, DatasetRevision
from datelier.inspection.presentation import (
    CellPresentation,
    NumericBounds,
    prepare_bounds,
    prepare_cell,
)
from datelier.io.types import ImportResult

PAGE_ROWS = 100
PAGE_COLUMNS = 16
CELL_CHARACTERS = 256


@dataclass(frozen=True)
class ColumnSummary:
    name: str
    dtype: str
    null_count: int


@dataclass(frozen=True)
class PreviewPage:
    revision: DatasetRevision
    row_start: int
    column_start: int
    columns: tuple[str, ...]
    row_ids: tuple[int, ...]
    rows: tuple[tuple[str, ...], ...]
    references: tuple[tuple[str | None, ...], ...] = ()
    cells: tuple[tuple[CellPresentation, ...], ...] = ()


@dataclass(frozen=True)
class Inspection:
    imported: ImportResult
    row_count: int
    schema: tuple[ColumnSummary, ...]
    first_page: PreviewPage
    bounds: tuple[NumericBounds, ...] = ()

    @property
    def dataset(self) -> Dataset:
        return self.imported.dataset


def _display_series(series: pl.Series) -> pl.Series:
    # Python temporal objects lose sub-microsecond precision. Format only the
    # bounded visible slice with Polars before converting cells to Python.
    dtype = series.dtype
    if isinstance(dtype, pl.Struct):
        return pl.select(
            pl.when(series.is_not_null())
            .then(pl.lit("{ ... }"))
            .otherwise(None)
            .alias(series.name)
        ).to_series()
    if isinstance(dtype, (pl.List, pl.Array)):
        lengths = series.list.len() if isinstance(dtype, pl.List) else series.arr.len()
        return pl.select(
            pl.when(series.is_not_null())
            .then(pl.lit("[ ... ] (") + lengths.cast(pl.String) + " items)")
            .otherwise(None)
            .alias(series.name)
        ).to_series()
    if isinstance(dtype, pl.Datetime):
        return series.cast(pl.String)
    if dtype == pl.Time:
        return series.dt.to_string("%H:%M:%S%.9f")
    if isinstance(dtype, pl.Duration):
        return series.cast(pl.Int64).cast(pl.String) + f" {dtype.time_unit}"
    return series


def prepare_page(
    dataset: Dataset, row_start: int, column_start: int = 0
) -> PreviewPage:
    table = dataset.table
    if row_start < 0 or column_start < 0 or column_start >= table.width:
        raise ValueError("Preview offsets must refer to valid rows/columns")
    columns = tuple(table.columns[column_start : column_start + PAGE_COLUMNS])
    # Names are data: select expressions would interpret ^...$
    # as regex selectors. Literal Series access also keeps the page bounded.
    visible = pl.DataFrame(
        [
            _display_series(table.get_column(name).slice(row_start, PAGE_ROWS))
            for name in columns
        ]
    )

    def cell(value: object) -> str:
        text = "NULL" if value is None else str(value)
        text = text.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
        return text if len(text) <= CELL_CHARACTERS else text[:CELL_CHARACTERS] + "…"

    physical_rows = tuple(
        table.select(
            [
                visible.get_column(n).alias(n)
                if table.schema[n].is_nested()
                else table.get_column(n).slice(row_start, PAGE_ROWS)
                for n in columns
            ]
        ).iter_rows()
    )
    roles = tuple(dataset.role(name).role for name in columns)
    return PreviewPage(
        dataset.revision,
        row_start,
        column_start,
        columns,
        tuple(dataset.row_ids.slice(row_start, PAGE_ROWS).to_list()),
        tuple(tuple(cell(value) for value in row) for row in visible.iter_rows()),
        tuple(
            tuple(
                value if isinstance(value, str) and role in REFERENCE_ROLES else None
                for role, value in zip(roles, row, strict=True)
            )
            for row in physical_rows
        ),
        tuple(
            tuple(
                prepare_cell(value, role)
                for role, value in zip(roles, row, strict=True)
            )
            for row in physical_rows
        ),
    )


def prepare_inspection(imported: ImportResult) -> Inspection:
    table = imported.dataset.table
    nulls = table.null_count().row(0)
    return Inspection(
        imported,
        table.height,
        tuple(
            ColumnSummary(name, str(dtype), int(count))
            for (name, dtype), count in zip(table.schema.items(), nulls, strict=True)
        ),
        prepare_page(imported.dataset, 0),
        prepare_bounds(imported.dataset),
    )
