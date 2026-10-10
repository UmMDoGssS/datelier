"""Explicit import drafts and default options, using path syntax only."""

from collections.abc import Callable
from pathlib import Path

from datelier.io.importing import detect_format
from datelier.io.types import (
    ArrayOptions,
    CheckpointOptions,
    CsvOptions,
    ImportFailure,
    ImportFormat,
    ImportOptions,
    JsonOptions,
    MediaOptions,
    ObjectOptions,
    ParquetOptions,
    XmlOptions,
)
from datelier.workspace.session_types import SourceDraft

DEFAULTS: dict[ImportFormat, Callable[[], ImportOptions]] = {
    ImportFormat.CSV: CsvOptions,
    ImportFormat.TSV: lambda: CsvOptions(separator="\t"),
    ImportFormat.JSON: JsonOptions,
    ImportFormat.JSONL: JsonOptions,
    ImportFormat.PARQUET: ParquetOptions,
    ImportFormat.XML: XmlOptions,
    ImportFormat.MEDIA: MediaOptions,
    ImportFormat.OBJECT: ObjectOptions,
    ImportFormat.ARRAY: ArrayOptions,
    ImportFormat.CHECKPOINT: CheckpointOptions,
}


def import_draft(
    path: Path, options: ImportOptions | None = None, format: ImportFormat | None = None
) -> SourceDraft:
    if format is None:
        try:
            format = detect_format(path)
        except ImportFailure:
            format = ImportFormat.MEDIA if not path.suffix else ImportFormat.CSV
    return SourceDraft(str(path), format, options or DEFAULTS[format]())
