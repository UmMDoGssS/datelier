"""Parquet imports preserve stored scalar types and explicit column choices."""

from pathlib import Path
from typing import BinaryIO

import polars as pl

from datelier.io.source import read_source
from datelier.io.types import ImportFormat, ImportResult, ParquetOptions


def load_parquet(path: Path, options: ParquetOptions | None = None) -> ImportResult:
    options = options or ParquetOptions()

    def read(source: BinaryIO) -> tuple[pl.DataFrame, tuple[str, ...]]:
        table = pl.read_parquet(
            source,
            columns=list(options.columns) if options.columns else None,
        )
        nested = [name for name, dtype in table.schema.items() if dtype.is_nested()]
        if nested:
            raise ValueError(
                f"Nested Parquet columns {nested!r} are unsupported; "
                "select scalar columns or flatten nested columns before importing."
            )
        diagnostics = ("Stored Parquet types preserved.",)
        if options.columns:
            diagnostics += (
                f"Only requested columns loaded: {list(options.columns)!r}.",
            )
        if table.height == 0:
            diagnostics += ("Parquet schema contains no data rows.",)
        return table, diagnostics

    return read_source(
        path,
        options,
        ImportFormat.PARQUET,
        read,
        "Check that the file is valid Parquet and requested columns exist.",
    )
