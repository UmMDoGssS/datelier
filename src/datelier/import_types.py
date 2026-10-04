"""Typed, GUI-independent import settings, results, and diagnostics."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from datelier.dataset import Dataset


class ImportFormat(StrEnum):
    CSV = "CSV"
    TSV = "TSV"


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


type ImportOptions = CsvOptions


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
