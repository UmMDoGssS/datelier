"""Local file format dispatch; adapters share prepared inspection state."""

from pathlib import Path

from datelier.import_csv import load_csv, load_tsv
from datelier.import_json import load_json
from datelier.import_parquet import load_parquet
from datelier.import_types import (
    CsvOptions,
    ImportFailure,
    ImportFormat,
    ImportOptions,
    ImportResult,
    JsonOptions,
    ParquetOptions,
    XmlOptions,
)
from datelier.import_xml import load_xml


def detect_format(path: Path) -> ImportFormat:
    formats = {
        ".csv": ImportFormat.CSV,
        ".tsv": ImportFormat.TSV,
        ".json": ImportFormat.JSON,
        ".jsonl": ImportFormat.JSONL,
        ".ndjson": ImportFormat.JSONL,
        ".parquet": ImportFormat.PARQUET,
        ".pq": ImportFormat.PARQUET,
        ".xml": ImportFormat.XML,
    }
    try:
        return formats[path.suffix.lower()]
    except KeyError as error:
        raise ImportFailure(
            path, "Unsupported extension; choose an import format."
        ) from error


def load_file(
    path: Path,
    options: ImportOptions | None = None,
    *,
    format: ImportFormat | None = None,
) -> ImportResult:
    selected = format if format is not None else detect_format(path)
    if selected == ImportFormat.XML:
        if options is not None and not isinstance(options, XmlOptions):
            raise ImportFailure(path, "XML requires XML import options.")
        return load_xml(path, options)
    if selected == ImportFormat.PARQUET:
        if options is not None and not isinstance(options, ParquetOptions):
            raise ImportFailure(path, "Parquet requires Parquet import options.")
        return load_parquet(path, options)
    if selected in (ImportFormat.JSON, ImportFormat.JSONL):
        if options is not None and not isinstance(options, JsonOptions):
            raise ImportFailure(path, "JSON/JSONL requires JSON import options.")
        return load_json(path, options, lines=selected == ImportFormat.JSONL)
    if options is not None and not isinstance(options, CsvOptions):
        raise ImportFailure(path, "CSV/TSV requires delimited import options.")
    settings = (
        options
        if options is not None
        else CsvOptions(separator="\t" if selected == ImportFormat.TSV else ",")
    )
    return (load_tsv if selected == ImportFormat.TSV else load_csv)(path, settings)
