"""Local file format dispatch; adapters share prepared inspection state."""

from pathlib import Path

from datelier.core.column_roles import (
    AUDIO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    TEXT_EXTENSIONS,
)
from datelier.io.arrays.importing import load_arrays
from datelier.io.csv import load_csv, load_tsv
from datelier.io.json import load_json
from datelier.io.media import load_media
from datelier.io.objects import load_object
from datelier.io.parquet import load_parquet
from datelier.io.types import (
    ArrayOptions,
    CsvOptions,
    ImportFailure,
    ImportFormat,
    ImportOptions,
    ImportResult,
    JsonOptions,
    MediaOptions,
    ObjectOptions,
    ParquetOptions,
    XmlOptions,
)
from datelier.io.xml import load_xml


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
        ".toml": ImportFormat.OBJECT,
        ".npy": ImportFormat.ARRAY,
        ".npz": ImportFormat.ARRAY,
    }
    if path.suffix.lower() in (*IMAGE_EXTENSIONS, *AUDIO_EXTENSIONS, *TEXT_EXTENSIONS):
        return ImportFormat.MEDIA
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
    selected = (
        format
        if format is not None
        else (ImportFormat.MEDIA if path.is_dir() else detect_format(path))
    )
    if selected == ImportFormat.ARRAY:
        if options is not None and not isinstance(options, ArrayOptions):
            raise ImportFailure(path, "Arrays require array import options.")
        return load_arrays(path, options)
    if selected == ImportFormat.OBJECT:
        if options is not None and not isinstance(options, ObjectOptions):
            raise ImportFailure(path, "Object sources require object import options.")
        return load_object(path, options)
    if selected == ImportFormat.MEDIA:
        if options is not None and not isinstance(options, MediaOptions):
            raise ImportFailure(
                path, "Media/text sources require media import options."
            )
        return load_media(path, options)
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


def load_inspectable_file(
    path: Path,
    options: ImportOptions | None = None,
    *,
    format: ImportFormat | None = None,
) -> ImportResult:
    """Editor opening preserves flat JSON defaults and browses other JSON shapes."""
    try:
        return load_file(path, options, format=format)
    except ImportFailure:
        if options is not None or format is not None or path.suffix.lower() != ".json":
            raise
        return load_object(path)
