"""Strict, read-only CSV import with an explicit Polars parsing contract."""

from pathlib import Path
from typing import BinaryIO

import polars as pl

from datelier.import_source import read_source, validate_utf8
from datelier.import_types import CsvOptions as CsvOptions
from datelier.import_types import ImportFailure as ImportFailure
from datelier.import_types import ImportFormat
from datelier.import_types import ImportResult as CsvImport


def load_csv(path: Path, options: CsvOptions | None = None) -> CsvImport:
    """Read UTF-8 without dropping bad rows or truncating extra fields.

    Empty files fail; header-only files retain an empty schema. Missing fields
    become null. Mixed columns infer as strings within the inference window;
    conflicting later values fail with advice to widen inference/read strings.
    """
    return _load_delimited(path, options or CsvOptions(), ImportFormat.CSV)


def load_tsv(path: Path, options: CsvOptions | None = None) -> CsvImport:
    """Read tab-separated records with the same strict options as CSV."""
    return _load_delimited(
        path, options or CsvOptions(separator="\t"), ImportFormat.TSV
    )


def _load_delimited(path: Path, options: CsvOptions, format: ImportFormat) -> CsvImport:
    def read(source: BinaryIO) -> tuple[pl.DataFrame, tuple[str, ...]]:
        validate_utf8(source)
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
        diagnostics = (
            (f"Header-only {format}: no data rows.",) if table.height == 0 else ()
        )
        if not options.infer_types:
            diagnostics += ("Type inference disabled: columns loaded as text.",)
        return table, diagnostics

    return read_source(
        path,
        options,
        format,
        read,
        "Check delimiter, quoting and field counts; for mixed types infer all rows "
        "or read columns as text.",
    )
