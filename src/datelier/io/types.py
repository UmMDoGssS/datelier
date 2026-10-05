"""Typed, GUI-independent import settings, results, and diagnostics."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from datelier.core.dataset import Dataset


class ImportFormat(StrEnum):
    CSV = "CSV"
    TSV = "TSV"
    JSON = "JSON"
    JSONL = "JSONL"
    PARQUET = "Parquet"
    XML = "XML"


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


@dataclass(frozen=True)
class JsonOptions:
    read_as_text: bool = False


@dataclass(frozen=True)
class ParquetOptions:
    columns: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.columns is not None and (
            not self.columns
            or len(set(self.columns)) != len(self.columns)
            or any(not name for name in self.columns)
        ):
            raise ValueError("Selected Parquet columns must be nonempty and unique")


@dataclass(frozen=True)
class XmlOptions:
    record_path: str = "./*"
    namespaces: tuple[tuple[str, str], ...] = ()
    include_attributes: bool = True
    strip_text: bool = True
    null_values: tuple[str, ...] = ()
    infer_types: bool = True
    try_parse_dates: bool = False

    def __post_init__(self) -> None:
        if not self.record_path.strip():
            raise ValueError("XML record path must be nonempty")
        prefixes = [prefix for prefix, _ in self.namespaces]
        if len(set(prefixes)) != len(prefixes) or any(
            not prefix or not uri for prefix, uri in self.namespaces
        ):
            raise ValueError("XML namespaces require unique nonempty prefixes and URIs")


type ImportOptions = CsvOptions | JsonOptions | ParquetOptions | XmlOptions


def validate_import_options(format: ImportFormat, options: ImportOptions) -> None:
    expected = {
        ImportFormat.CSV: CsvOptions,
        ImportFormat.TSV: CsvOptions,
        ImportFormat.JSON: JsonOptions,
        ImportFormat.JSONL: JsonOptions,
        ImportFormat.PARQUET: ParquetOptions,
        ImportFormat.XML: XmlOptions,
    }[format]
    if type(options) is not expected:
        raise ValueError("Import options do not match the saved format")


def validate_source_path(path: str) -> None:
    path.encode("utf8")
    if not path.strip() or "\x00" in path or len(path) > 4096:
        raise ValueError("Invalid source reference path")


class ImportFailure(Exception):
    """An actionable failure that callers can display without a traceback."""

    def __init__(self, path: Path, message: str) -> None:
        self.path = path
        super().__init__(f"{path.name}: {message}")


@dataclass(frozen=True)
class ImportResult:
    dataset: Dataset
    options: ImportOptions
    diagnostics: tuple[str, ...]
    format: ImportFormat = ImportFormat.CSV
