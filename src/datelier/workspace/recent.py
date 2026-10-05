"""Bounded source references and successful import recipes for recent opening."""

from dataclasses import dataclass
from enum import StrEnum

from datelier.io.types import (
    ImportFormat,
    ImportOptions,
    validate_import_options,
    validate_source_path,
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
        validate_source_path(self.path)
        if self.source_kind == RecentKind.WORKSPACE:
            if self.format is not None or self.options is not None:
                raise ValueError("Workspace entries cannot have import options")
            return
        if self.format is None or self.options is None:
            raise ValueError("Recent files require matching format and options")
        validate_import_options(self.format, self.options)


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
