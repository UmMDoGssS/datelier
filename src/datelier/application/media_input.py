"""Prepared, scoped inputs shared by media controllers; no GUI objects."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from datelier.inspection.records.types import InspectSettings, RecordSet
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.table import Inspection
from datelier.io.arrays.storage import ArrayStore


@dataclass(frozen=True)
class MediaInput:
    file_id: str
    view_name: str
    active: Inspection | None
    references: ReferenceSettings
    index: ReferenceIndex | None
    selected_rows: tuple[int, ...]
    arrays: ArrayStore
    inspect: InspectSettings
    records: RecordSet | None


class MediaController(ABC):
    @abstractmethod
    def sync(self, source: MediaInput) -> None: ...

    @abstractmethod
    def close(self) -> None: ...
