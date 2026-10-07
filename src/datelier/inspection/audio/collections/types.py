"""Scalar record/channel outcomes with complete source provenance, no payload cache."""

from dataclasses import dataclass
from threading import Lock

import polars as pl

from datelier.core.dataset import DatasetRevision, SourceReference
from datelier.inspection.arrays.mapping import ArrayRecordMapping
from datelier.inspection.audio.collections.settings import AudioCollectionSettings


class CollectionProgress:
    def __init__(self) -> None:
        self._lock = Lock()
        self._value = ("", 0, 0)

    @property
    def value(self) -> tuple[str, int, int]:
        with self._lock:
            return self._value

    def update(self, phase: str, done: int, total: int) -> None:
        with self._lock:
            self._value = phase, done, total


@dataclass(frozen=True)
class AudioCollectionProfile:
    file_id: str
    view_name: str
    revision: DatasetRevision
    source: SourceReference
    settings: AudioCollectionSettings
    mapping: ArrayRecordMapping | None
    available_records: int
    records: pl.DataFrame
    channel_records: pl.DataFrame
    ready: int
    nulls: int
    failures: int

    @property
    def retained_bytes(self) -> int:
        return int(
            self.records.estimated_size() + self.channel_records.estimated_size()
        )
