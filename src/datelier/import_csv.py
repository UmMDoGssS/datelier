"""Strict, read-only CSV import with an explicit Polars parsing contract."""

from pathlib import Path

import polars as pl

from datelier.dataset import Dataset, SourceReference
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
            path, f"No {format} data found; supply a header or records."
        ) from error
    except pl.exceptions.PolarsError as error:
        detail = str(error)[:1200]
        raise ImportFailure(
            path,
            f"Could not parse {format}. Check delimiter, quoting and field counts; "
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
    diagnostics = (f"Header-only {format}: no data rows.",) if table.height == 0 else ()
    if not options.infer_types:
        diagnostics += ("Type inference disabled: columns loaded as text.",)
    return CsvImport(
        Dataset.from_source(
            table, SourceReference(path, after.st_size, after.st_mtime_ns)
        ),
        options,
        diagnostics,
        format,
    )
