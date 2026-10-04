"""Read-only local source guard shared by format adapters."""

from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

import polars as pl

from datelier.dataset import Dataset, SourceReference
from datelier.import_types import (
    ImportFailure,
    ImportFormat,
    ImportOptions,
    ImportResult,
)


def read_source(
    path: Path,
    options: ImportOptions,
    format: ImportFormat,
    reader: Callable[[BinaryIO], tuple[pl.DataFrame, tuple[str, ...]]],
    advice: str,
) -> ImportResult:
    path = path.expanduser().resolve()
    try:
        before = path.stat()
        with path.open("rb") as source:
            table, diagnostics = reader(source)
        after = path.stat()
    except ImportFailure:
        raise
    except (
        pl.exceptions.PolarsError,
        ValueError,
        UnicodeError,
        RecursionError,
    ) as error:
        raise ImportFailure(
            path, f"Could not parse {format}. {advice} {str(error)[:1200]}"
        ) from error
    except OSError as error:
        raise ImportFailure(
            path, f"Could not read source: {error.strerror}."
        ) from error
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size,
        after.st_mtime_ns,
        after.st_ino,
    ):
        raise ImportFailure(path, "Source changed during import; reload the file.")
    if table.width == 0:
        raise ImportFailure(
            path, f"No {format} columns found; supply tabular records with fields."
        )
    return ImportResult(
        Dataset.from_source(
            table, SourceReference(path, after.st_size, after.st_mtime_ns)
        ),
        options,
        diagnostics,
        format,
    )
