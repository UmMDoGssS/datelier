"""Strict, read-only CSV import with an explicit Polars parsing contract."""

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from datelier.dataset import Dataset, SourceReference


@dataclass(frozen=True)
class CsvOptions:
    separator: str = ","
    has_header: bool = True
    quote_char: str | None = '"'
    null_values: tuple[str, ...] = ()
    infer_schema_length: int | None = 100
    infer_types: bool = True
    try_parse_dates: bool = False
    skip_rows: int = 0

    def __post_init__(self) -> None:
        for name, value in (("Separator", self.separator), ("Quote", self.quote_char)):
            if value is not None and (
                len(value.encode("utf8")) != 1 or value in "\r\n\x00"
            ):
                raise ValueError(f"{name} must be a single non-newline UTF-8 byte")
        if self.infer_schema_length is not None and self.infer_schema_length < 1:
            raise ValueError("Schema inference rows must be positive or all rows")
        if self.skip_rows < 0:
            raise ValueError("Skipped rows must be nonnegative")


class ImportFailure(Exception):
    """An actionable failure that callers can display without a traceback."""

    def __init__(self, path: Path, message: str) -> None:
        self.path = path
        super().__init__(f"{path.name}: {message}")


@dataclass(frozen=True)
class CsvImport:
    dataset: Dataset
    options: CsvOptions
    diagnostics: tuple[str, ...]


def load_csv(path: Path, options: CsvOptions | None = None) -> CsvImport:
    """Read UTF-8 without dropping bad rows or truncating extra fields.

    Empty files fail; header-only files retain an empty schema. Missing fields
    become null. Mixed columns infer as strings within the inference window;
    conflicting later values fail with advice to widen inference/read strings.
    """
    options = options if options is not None else CsvOptions()
    path = path.expanduser().resolve()
    try:
        before = path.stat()
        with path.open("rb") as source:
            table = pl.read_csv(
                source,
                separator=options.separator,
                has_header=options.has_header,
                quote_char=options.quote_char,
                null_values=list(options.null_values) or None,
                infer_schema_length=options.infer_schema_length,
                infer_schema=options.infer_types,
                try_parse_dates=options.try_parse_dates,
                skip_rows=options.skip_rows,
                encoding="utf8",
                ignore_errors=False,
                truncate_ragged_lines=False,
            )
        after = path.stat()
    except pl.exceptions.NoDataError as error:
        raise ImportFailure(
            path, "No CSV data found; supply a header or records."
        ) from error
    except pl.exceptions.PolarsError as error:
        detail = str(error)[:1200]
        raise ImportFailure(
            path,
            "Could not parse CSV. Check delimiter, quoting and field counts; "
            "for mixed types infer all rows or read columns as text. " + detail,
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
    diagnostics = ("Header-only CSV: no data rows.",) if table.height == 0 else ()
    if not options.infer_types:
        diagnostics += ("Type inference disabled: columns loaded as text.",)
    return CsvImport(
        Dataset.from_source(
            table, SourceReference(path, after.st_size, after.st_mtime_ns)
        ),
        options,
        diagnostics,
    )
