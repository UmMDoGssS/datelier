"""Bounded source references and successful import recipes for recent opening."""

from dataclasses import dataclass
from enum import StrEnum

from datelier.io.types import (
    CsvOptions,
    ImportFormat,
    ImportOptions,
    JsonOptions,
    ParquetOptions,
    XmlOptions,
)

MAX_RECENT = 20


class RecentKind(StrEnum):
    FILE = "File"
    WORKSPACE = "Workspace"


@dataclass(frozen=True)
class RecentSource:
    path: str
    source_kind: RecentKind = RecentKind.FILE
    format: ImportFormat | None = None
    options: ImportOptions | None = None

    def __post_init__(self) -> None:
        self.path.encode("utf8")
        if not self.path.strip() or "\x00" in self.path or len(self.path) > 4096:
            raise ValueError("Invalid recent source path")
        if self.source_kind == RecentKind.WORKSPACE:
            if self.format is not None or self.options is not None:
                raise ValueError("Workspace entries cannot have import options")
            return
        expected = {
            ImportFormat.CSV: CsvOptions,
            ImportFormat.TSV: CsvOptions,
            ImportFormat.JSON: JsonOptions,
            ImportFormat.JSONL: JsonOptions,
            ImportFormat.PARQUET: ParquetOptions,
            ImportFormat.XML: XmlOptions,
        }
        if self.format is None or type(self.options) is not expected[self.format]:
            raise ValueError("Recent files require matching format and options")


def remember(
    entries: tuple[RecentSource, ...], source: RecentSource
) -> tuple[RecentSource, ...]:
    return (
        source,
        *(
            entry
            for entry in entries
            if (entry.source_kind, entry.path) != (source.source_kind, source.path)
        ),
    )[:MAX_RECENT]
