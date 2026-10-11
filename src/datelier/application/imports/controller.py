"""One source's independent option drafts and explicit request boundary."""

from collections.abc import Callable
from pathlib import Path

from datelier.application.imports.base import OptionsDraft
from datelier.application.imports.drafts import import_draft
from datelier.application.imports.media import MediaDraft
from datelier.application.imports.structured import (
    ArrayDraft,
    CheckpointDraft,
    ObjectDraft,
)
from datelier.application.imports.tabular import (
    DelimitedDraft,
    JsonDraft,
    ParquetDraft,
    XmlDraft,
)
from datelier.io.importing import detect_format
from datelier.io.types import ImportFailure, ImportFormat, validate_source_path
from datelier.workspace.sessions import SourceDraft


class ImportController:
    def __init__(self, request: Callable[[SourceDraft], None]) -> None:
        self._request = request
        self.path = ""
        self.format: ImportFormat | None = None
        self.csv, self.tsv = DelimitedDraft(), DelimitedDraft("\t")
        self.json, self.jsonl = JsonDraft(), JsonDraft()
        self.parquet, self.xml = ParquetDraft(), XmlDraft()
        self.media, self.objects = MediaDraft(), ObjectDraft()
        self.arrays, self.checkpoints = ArrayDraft(), CheckpointDraft()
        self.drafts: dict[ImportFormat, OptionsDraft] = {
            ImportFormat.CSV: self.csv,
            ImportFormat.TSV: self.tsv,
            ImportFormat.JSON: self.json,
            ImportFormat.JSONL: self.jsonl,
            ImportFormat.PARQUET: self.parquet,
            ImportFormat.XML: self.xml,
            ImportFormat.MEDIA: self.media,
            ImportFormat.OBJECT: self.objects,
            ImportFormat.ARRAY: self.arrays,
            ImportFormat.CHECKPOINT: self.checkpoints,
        }
        self.busy = self.blocked = self.closed = False
        self._bound: SourceDraft | None = None

    @property
    def selected(self) -> ImportFormat | None:
        if self.format:
            return self.format
        if not self.path.strip():
            return None
        try:
            return detect_format(Path(self.path))
        except ImportFailure:
            return ImportFormat.MEDIA if not Path(self.path).suffix else None

    def bind(self, draft: SourceDraft | None) -> None:
        if draft is None or draft == self._bound:
            return
        draft.validate()
        self._bound = draft
        self.restore(draft)

    def restore(self, draft: SourceDraft) -> None:
        draft.validate()
        self.path, self.format = draft.path, draft.format
        self.drafts[draft.format].bind(draft.options)

    def capture(self) -> SourceDraft | None:
        if not self.path.strip():
            return None
        validate_source_path(self.path)
        selected = self.selected
        if selected is None:
            raise ValueError("Choose an import format for this source extension")
        draft = import_draft(Path(self.path), self.drafts[selected].build(), selected)
        draft.validate()
        return draft

    def request(self) -> None:
        if self.closed or self.blocked or self.busy:
            raise ValueError("Finish loading or source recovery before importing")
        draft = self.capture()
        if draft is None:
            raise ValueError("Enter a source file or folder path")
        self._request(draft)

    def close(self) -> None:
        self.closed = True
        self._request = lambda _: None
